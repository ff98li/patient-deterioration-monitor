"""
Lab Producer: Streams patient lab results from CSV to Kafka

This script reads the MIMIC-IV lab results export and sends each record
to Confluent Kafka, simulating real-time lab data arriving from the hospital lab.
"""

import json
import time
import pandas as pd
from confluent_kafka import Producer
from datetime import datetime, UTC

import config


# Lab-specific configuration
LABS_TOPIC = "patient-labs"
LABS_FILE = "data/patient_labs.csv"


def create_producer():
    """Create and configure Kafka producer for Confluent Cloud."""
    conf = {
        'bootstrap.servers': config.CONFLUENT_BOOTSTRAP_SERVER,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': config.CONFLUENT_API_KEY,
        'sasl.password': config.CONFLUENT_API_SECRET,
        'client.id': 'patient-labs-producer'
    }
    return Producer(conf)


def delivery_callback(err, msg):
    """Callback for message delivery confirmation."""
    if err is not None:
        print(f'❌ Message delivery failed: {err}')
    else:
        print(f'🧪 Sent: {msg.key().decode("utf-8")} -> {msg.topic()}')


def load_labs_data(filepath: str) -> pd.DataFrame:
    """Load and prepare lab data from CSV."""
    print(f"Loading lab data from {filepath}...")
    df = pd.read_csv(filepath)
    
    # Ensure proper column types
    df['charttime'] = pd.to_datetime(df['charttime'])
    df = df.sort_values(['stay_id', 'charttime'])
    
    print(f"Loaded {len(df)} lab result records")
    print(f"Unique patients (stay_ids): {df['stay_id'].nunique()}")
    print(f"Lab types: {df['lab_type'].unique().tolist()}")
    
    return df


def stream_labs(producer: Producer, df: pd.DataFrame, delay: float = 0.05):
    """
    Stream lab results to Kafka topic.
    
    Groups labs by timestamp to simulate realistic lab processing where
    multiple labs from the same blood draw arrive together.
    """
    records_sent = 0
    
    print(f"\n🧪 Starting to stream labs to topic: {LABS_TOPIC}")
    print(f"   Delay between records: {delay}s")
    print("-" * 50)
    
    # Group by stay_id and charttime to send concurrent labs together
    for (stay_id, charttime), group in df.groupby(['stay_id', 'charttime']):
        
        # Create a message with all labs at this timestamp
        labs_at_time = {}
        units = {}
        for _, row in group.iterrows():
            labs_at_time[row['lab_type']] = row['lab_value']
            units[row['lab_type']] = row['unit']
        
        message = {
            'subject_id': int(group.iloc[0]['subject_id']),
            'stay_id': int(stay_id),
            'timestamp': charttime.isoformat(),
            'labs': labs_at_time,
            'units': units,
            'produced_at': datetime.now(UTC).isoformat()
        }
        
        # Send to Kafka
        producer.produce(
            topic=LABS_TOPIC,
            key=str(stay_id),
            value=json.dumps(message),
            callback=delivery_callback
        )
        
        records_sent += 1
        
        # Flush periodically to ensure delivery
        if records_sent % 100 == 0:
            producer.flush()
            print(f"   Streamed {records_sent} lab groups...")
        
        # Simulate real-time delay (labs arrive less frequently than vitals)
        time.sleep(delay)
    
    # Final flush
    producer.flush()
    print("-" * 50)
    print(f"✅ Completed! Sent {records_sent} lab result groups to Kafka")


def main():
    """Main entry point."""
    print("=" * 50)
    print("Patient Labs Producer")
    print("=" * 50)
    
    # Load data
    df = load_labs_data(LABS_FILE)
    
    # Create producer
    producer = create_producer()
    print(f"\n✓ Connected to Confluent Cloud")
    print(f"  Server: {config.CONFLUENT_BOOTSTRAP_SERVER}")
    
    # Stream data
    try:
        stream_labs(
            producer=producer,
            df=df,
            delay=0.05  # Labs arrive faster in simulation since there are fewer
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        producer.flush()
        print("Producer shut down cleanly")


if __name__ == "__main__":
    main()
