"""
Continuous Vitals Producer for Production Deployment

Reads long-format CSV (one vital per row) and streams to Kafka.
Loops forever for continuous demo.
"""

import json
import time
import pandas as pd
from datetime import datetime, timezone
from confluent_kafka import Producer

import config


def delivery_callback(err, msg):
    if err:
        print(f'❌ Delivery failed: {err}')


def create_producer():
    conf = {
        'bootstrap.servers': config.CONFLUENT_BOOTSTRAP_SERVER,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': config.CONFLUENT_API_KEY,
        'sasl.password': config.CONFLUENT_API_SECRET,
        'client.id': 'patient-vitals-producer'
    }
    return Producer(conf)


def load_vitals_data(filepath='data/patient_vitals.csv'):
    """Load long-format vitals data."""
    df = pd.read_csv(filepath)
    df['charttime'] = pd.to_datetime(df['charttime'])
    df = df.sort_values(['stay_id', 'charttime'])
    return df


def produce_vitals(producer, df, topic='patient-vitals', delay=0.05):
    """Stream vitals data to Kafka, grouping by stay_id and charttime."""
    
    # Group by stay_id and charttime
    grouped = df.groupby(['stay_id', 'charttime'])
    
    count = 0
    for (stay_id, charttime), group in grouped:
        # Build vitals dict from long format
        vitals = {}
        subject_id = None
        
        for _, row in group.iterrows():
            subject_id = row['subject_id']
            vital_type = row['vital_type']
            vital_value = row['vital_value']
            
            if pd.notna(vital_value):
                vitals[vital_type] = float(vital_value)
        
        if not vitals:
            continue
        
        message = {
            'subject_id': int(subject_id) if subject_id else 0,
            'stay_id': int(stay_id),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'vitals': vitals,
            'produced_at': datetime.now(timezone.utc).isoformat()
        }
        
        producer.produce(
            topic,
            key=str(stay_id),
            value=json.dumps(message),
            callback=delivery_callback
        )
        
        count += 1
        if count % 100 == 0:
            producer.flush()
            print(f"📤 Sent {count} vitals records...")
        
        time.sleep(delay)
    
    producer.flush()
    return count


def main():
    print("=" * 60)
    print("Patient Vitals Producer - CONTINUOUS MODE")
    print("=" * 60)
    
    producer = create_producer()
    print(f"✓ Connected to Confluent Cloud")
    
    df = load_vitals_data()
    print(f"✓ Loaded {len(df)} vitals records")
    print(f"✓ Unique patients: {df['stay_id'].nunique()}")
    
    loop_count = 0
    
    while True:
        loop_count += 1
        print(f"\n🔄 Starting loop #{loop_count}...")
        
        try:
            count = produce_vitals(producer, df)
            print(f"✓ Completed loop #{loop_count}: sent {count} records")
        except Exception as e:
            print(f"❌ Error in loop #{loop_count}: {e}")
        
        print("⏳ Waiting 10 seconds before next loop...")
        time.sleep(10)


if __name__ == "__main__":
    main()
