"""
Producer: Streams patient vital signs from CSV to Kafka

This script reads the MIMIC-IV vital signs export and sends each record
to Confluent Kafka, simulating real-time patient monitoring data.
"""

import json
import time
import pandas as pd
from confluent_kafka import Producer
from datetime import datetime

import config


def create_producer():
    """Create and configure Kafka producer for Confluent Cloud."""
    conf = {
        'bootstrap.servers': config.CONFLUENT_BOOTSTRAP_SERVER,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': config.CONFLUENT_API_KEY,
        'sasl.password': config.CONFLUENT_API_SECRET,
        'client.id': 'patient-vitals-producer'
    }
    return Producer(conf)


def delivery_callback(err, msg):
    """Callback for message delivery confirmation."""
    if err is not None:
        print(f'❌ Message delivery failed: {err}')
    else:
        print(f'✓ Sent: {msg.key().decode("utf-8")} -> {msg.topic()}')


def load_vitals_data(filepath: str) -> pd.DataFrame:
    """Load and prepare vitals data from CSV."""
    print(f"Loading data from {filepath}...")
    df = pd.read_csv(filepath)
    
    # Ensure proper column types
    df['charttime'] = pd.to_datetime(df['charttime'])
    df = df.sort_values(['stay_id', 'charttime'])
    
    print(f"Loaded {len(df)} vital sign records")
    print(f"Unique patients (stay_ids): {df['stay_id'].nunique()}")
    print(f"Vital types: {df['vital_type'].unique().tolist()}")
    
    return df


def stream_vitals(producer: Producer, df: pd.DataFrame, delay: float = 0.1):
    """
    Stream vital signs to Kafka topic.
    
    Groups vitals by timestamp to simulate realistic monitoring where
    multiple vitals are recorded at the same time.
    """
    topic = config.KAFKA_TOPIC
    records_sent = 0
    
    print(f"\n🚀 Starting to stream vitals to topic: {topic}")
    print(f"   Delay between records: {delay}s")
    print("-" * 50)
    
    # Group by stay_id and charttime to send concurrent vitals together
    for (stay_id, charttime), group in df.groupby(['stay_id', 'charttime']):
        
        # Create a message with all vitals at this timestamp
        vitals_at_time = {}
        for _, row in group.iterrows():
            vitals_at_time[row['vital_type']] = row['vital_value']
        
        message = {
            'subject_id': int(group.iloc[0]['subject_id']),
            'stay_id': int(stay_id),
            'timestamp': charttime.isoformat(),
            'vitals': vitals_at_time,
            'produced_at': datetime.utcnow().isoformat()
        }
        
        # Send to Kafka
        producer.produce(
            topic=topic,
            key=str(stay_id),
            value=json.dumps(message),
            callback=delivery_callback
        )
        
        records_sent += 1
        
        # Flush periodically to ensure delivery
        if records_sent % 100 == 0:
            producer.flush()
            print(f"   Streamed {records_sent} timestamp groups...")
        
        # Simulate real-time delay
        time.sleep(delay)
    
    # Final flush
    producer.flush()
    print("-" * 50)
    print(f"✅ Completed! Sent {records_sent} vital sign groups to Kafka")


def main():
    """Main entry point."""
    print("=" * 50)
    print("Patient Vitals Producer")
    print("=" * 50)
    
    # Load data
    df = load_vitals_data('data/patient_vitals.csv')
    
    # Create producer
    producer = create_producer()
    print(f"\n✓ Connected to Confluent Cloud")
    print(f"  Server: {config.CONFLUENT_BOOTSTRAP_SERVER}")
    
    # Stream data
    try:
        stream_vitals(
            producer=producer,
            df=df,
            delay=config.STREAM_DELAY_SECONDS
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        producer.flush()
        print("Producer shut down cleanly")


if __name__ == "__main__":
    main()
