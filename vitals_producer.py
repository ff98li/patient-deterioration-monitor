"""
Vitals Producer: Streams patient vital signs from BigQuery to Kafka

This script queries MIMIC-IV vital signs directly from BigQuery and sends 
each record to Confluent Kafka, simulating real-time patient monitoring data.

Non-continuous version - runs through data once and exits.
"""

import json
import time
from datetime import datetime, timezone
from confluent_kafka import Producer
from google.cloud import bigquery
from collections import defaultdict

import config


# BigQuery SQL matching patient_vitals_500.sql
VITALS_QUERY = """
WITH vital_mappings AS (
  SELECT *
  FROM UNNEST([
    STRUCT(220045 AS itemid, 'heart_rate' AS vital_type),
    STRUCT(220050 AS itemid, 'systolic_bp' AS vital_type),
    STRUCT(220051 AS itemid, 'diastolic_bp' AS vital_type),
    STRUCT(220052 AS itemid, 'mean_arterial_pressure' AS vital_type),
    STRUCT(220179 AS itemid, 'systolic_bp' AS vital_type),
    STRUCT(220180 AS itemid, 'diastolic_bp' AS vital_type),
    STRUCT(220181 AS itemid, 'mean_arterial_pressure' AS vital_type),
    STRUCT(220210 AS itemid, 'respiratory_rate' AS vital_type),
    STRUCT(224690 AS itemid, 'respiratory_rate' AS vital_type),
    STRUCT(220277 AS itemid, 'spo2' AS vital_type),
    STRUCT(223761 AS itemid, 'temperature_f' AS vital_type),
    STRUCT(223762 AS itemid, 'temperature_c' AS vital_type)
  ])
),

sample_stays AS (
  SELECT DISTINCT stay_id
  FROM `physionet-data.mimiciv_3_1_icu.icustays`
  ORDER BY stay_id
  LIMIT 500
),

vitals AS (
  SELECT 
    ce.subject_id,
    ce.stay_id,
    ce.charttime,
    vm.vital_type,
    ce.valuenum AS vital_value
  FROM `physionet-data.mimiciv_3_1_icu.chartevents` ce
  INNER JOIN sample_stays ss ON ce.stay_id = ss.stay_id
  INNER JOIN vital_mappings vm ON ce.itemid = vm.itemid
  WHERE ce.valuenum IS NOT NULL
    AND ce.valuenum > 0
    AND (
      (vm.vital_type = 'heart_rate' AND ce.valuenum BETWEEN 20 AND 300) OR
      (vm.vital_type = 'systolic_bp' AND ce.valuenum BETWEEN 40 AND 300) OR
      (vm.vital_type = 'diastolic_bp' AND ce.valuenum BETWEEN 20 AND 200) OR
      (vm.vital_type = 'mean_arterial_pressure' AND ce.valuenum BETWEEN 30 AND 250) OR
      (vm.vital_type = 'respiratory_rate' AND ce.valuenum BETWEEN 4 AND 60) OR
      (vm.vital_type = 'spo2' AND ce.valuenum BETWEEN 50 AND 100) OR
      (vm.vital_type = 'temperature_f' AND ce.valuenum BETWEEN 90 AND 110) OR
      (vm.vital_type = 'temperature_c' AND ce.valuenum BETWEEN 32 AND 43)
    )
)

SELECT 
  subject_id,
  stay_id,
  charttime,
  vital_type,
  vital_value
FROM vitals
ORDER BY stay_id, charttime, vital_type
"""


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


def load_vitals_from_bigquery():
    """Load vitals data from BigQuery and group by (stay_id, charttime)."""
    
    client = bigquery.Client(project=config.GCP_PROJECT_ID)
    
    print("📊 Querying MIMIC-IV Vitals from BigQuery...")
    print("   (This may take 30-60 seconds for initial query)")
    
    query_job = client.query(VITALS_QUERY)
    results = query_job.result()
    
    # Group by (stay_id, charttime) like the CSV version
    vitals_by_time = defaultdict(lambda: {
        'subject_id': None,
        'stay_id': None,
        'charttime': None,
        'vitals': {}
    })
    
    row_count = 0
    unique_patients = set()
    
    for row in results:
        key = (row.stay_id, row.charttime)
        vitals_by_time[key]['subject_id'] = row.subject_id
        vitals_by_time[key]['stay_id'] = row.stay_id
        vitals_by_time[key]['charttime'] = row.charttime
        
        vital_type = row.vital_type
        vital_value = row.vital_value
        
        if vital_type and vital_value is not None:
            vitals_by_time[key]['vitals'][vital_type] = round(float(vital_value), 2)
        
        unique_patients.add(row.stay_id)
        row_count += 1
    
    # Convert to list and sort
    vitals_list = list(vitals_by_time.values())
    vitals_list.sort(key=lambda x: (x['stay_id'], x['charttime'] or datetime.min))
    
    print(f"✓ Loaded {row_count} vital sign records")
    print(f"✓ Unique patients (stay_ids): {len(unique_patients)}")
    print(f"✓ Grouped into {len(vitals_list)} timestamp groups")
    
    return vitals_list


def stream_vitals(producer: Producer, vitals_list: list, delay: float = None):
    """
    Stream vital signs to Kafka topic.
    
    Groups vitals by timestamp to simulate realistic monitoring where
    multiple vitals are recorded at the same time.
    """
    if delay is None:
        delay = config.STREAM_DELAY_SECONDS
        
    topic = config.KAFKA_TOPIC
    records_sent = 0
    
    print(f"\n🚀 Starting to stream vitals to topic: {topic}")
    print(f"   Delay between records: {delay}s")
    print("-" * 50)
    
    for record in vitals_list:
        vitals = record['vitals']
        
        if not vitals:
            continue
        
        message = {
            'subject_id': int(record['subject_id']) if record['subject_id'] else 0,
            'stay_id': int(record['stay_id']),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'vitals': vitals,
            'produced_at': datetime.now(timezone.utc).isoformat()
        }
        
        producer.produce(
            topic=topic,
            key=str(record['stay_id']),
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
    
    return records_sent


def main():
    """Main entry point."""
    print("=" * 50)
    print("Patient Vitals Producer - BigQuery Version")
    print("=" * 50)
    
    # Load data from BigQuery
    vitals_list = load_vitals_from_bigquery()
    
    # Create producer
    producer = create_producer()
    print(f"\n✓ Connected to Confluent Cloud")
    print(f"  Server: {config.CONFLUENT_BOOTSTRAP_SERVER}")
    
    # Stream data
    try:
        stream_vitals(
            producer=producer,
            vitals_list=vitals_list,
            delay=config.STREAM_DELAY_SECONDS
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        producer.flush()
        print("Producer shut down cleanly")


if __name__ == "__main__":
    main()
