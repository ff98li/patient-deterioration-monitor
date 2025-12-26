"""
Continuous Labs Producer for Production Deployment

Reads long-format CSV (one lab per row) and streams to Kafka.
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
        'client.id': 'patient-labs-producer'
    }
    return Producer(conf)


def load_labs_data(filepath='data/patient_labs.csv'):
    """Load long-format labs data."""
    df = pd.read_csv(filepath)
    df['charttime'] = pd.to_datetime(df['charttime'])
    df = df.sort_values(['stay_id', 'charttime'])
    return df


def produce_labs(producer, df, topic='patient-labs', delay=0.1):
    """Stream labs data to Kafka, grouping by stay_id and charttime."""
    
    # Group by stay_id and charttime
    grouped = df.groupby(['stay_id', 'charttime'])
    
    count = 0
    for (stay_id, charttime), group in grouped:
        # Build labs dict from long format
        labs = {}
        units = {}
        subject_id = None
        
        for _, row in group.iterrows():
            subject_id = row['subject_id']
            lab_type = row['lab_type']
            lab_value = row['lab_value']
            unit = row.get('unit', '')
            
            if pd.notna(lab_value):
                labs[lab_type] = float(lab_value)
                units[lab_type] = unit if pd.notna(unit) else ''
        
        if not labs:
            continue
        
        message = {
            'subject_id': int(subject_id) if subject_id else 0,
            'stay_id': int(stay_id),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'labs': labs,
            'units': units,
            'produced_at': datetime.now(timezone.utc).isoformat()
        }
        
        producer.produce(
            topic,
            key=str(stay_id),
            value=json.dumps(message),
            callback=delivery_callback
        )
        
        count += 1
        if count % 50 == 0:
            producer.flush()
            print(f"🧪 Sent {count} lab records...")
        
        time.sleep(delay)
    
    producer.flush()
    return count


def main():
    print("=" * 60)
    print("Patient Labs Producer - CONTINUOUS MODE")
    print("=" * 60)
    
    producer = create_producer()
    print(f"✓ Connected to Confluent Cloud")
    
    df = load_labs_data()
    print(f"✓ Loaded {len(df)} lab records")
    print(f"✓ Unique patients: {df['stay_id'].nunique()}")
    
    loop_count = 0
    
    while True:
        loop_count += 1
        print(f"\n🔄 Starting loop #{loop_count}...")
        
        try:
            count = produce_labs(producer, df)
            print(f"✓ Completed loop #{loop_count}: sent {count} records")
        except Exception as e:
            print(f"❌ Error in loop #{loop_count}: {e}")
        
        print("⏳ Waiting 10 seconds before next loop...")
        time.sleep(10)


if __name__ == "__main__":
    main()
