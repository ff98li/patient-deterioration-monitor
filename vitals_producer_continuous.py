"""
Continuous Vitals Producer - BigQuery Version

Streams vital signs directly from MIMIC-IV BigQuery dataset to Confluent Kafka.
Loops forever for continuous demo.

Uses the same SQL logic as patient_vitals_500.sql
"""

import json
import time
from datetime import datetime, timezone
from confluent_kafka import Producer
from google.cloud import bigquery
from collections import defaultdict

import config


# BigQuery SQL matching patient_vitals_500.sql exactly
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


def load_vitals_from_bigquery():
    """Load vitals data from BigQuery and group by (stay_id, charttime)."""
    
    client = bigquery.Client(project=config.GCP_PROJECT_ID)
    
    print("📊 Querying MIMIC-IV Vitals from BigQuery...")
    print("   (This may take 10-30 seconds for initial query)")
    
    query_job = client.query(VITALS_QUERY)
    results = query_job.result()
    
    # Group by (stay_id, charttime) like the CSV version
    vitals_by_time = defaultdict(lambda: {
        'subject_id': None,
        'stay_id': None,
        'charttime': None,
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
            vitals_by_time[key][vital_type] = round(float(vital_value), 1)
        
        unique_patients.add(row.stay_id)
        row_count += 1
    
    # Convert to list and sort
    vitals_list = list(vitals_by_time.values())
    vitals_list.sort(key=lambda x: (x['stay_id'], x['charttime'] or datetime.min))
    
    print(f"✓ Loaded {row_count} vital records")
    print(f"✓ Unique patients: {len(unique_patients)}")
    print(f"✓ Grouped into {len(vitals_list)} timestamp groups")
    
    return vitals_list


def produce_vitals(producer, vitals_list, topic='patient-vitals', delay=0.05):
    """Stream vitals data to Kafka, matching CSV producer format."""
    
    count = 0
    
    # All possible vital types from the SQL
    vital_keys = [
        'heart_rate', 'respiratory_rate', 'spo2', 
        'systolic_bp', 'diastolic_bp', 'mean_arterial_pressure',
        'temperature_f', 'temperature_c'
    ]
    
    for record in vitals_list:
        # Build vitals dict (only non-None values)
        vitals = {}
        for key in vital_keys:
            if key in record and record[key] is not None:
                vitals[key] = record[key]
        
        if not vitals:
            continue
        
        # Match the CSV producer message format exactly
        message = {
            'subject_id': int(record['subject_id']) if record['subject_id'] else 0,
            'stay_id': int(record['stay_id']),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'vitals': vitals,
            'produced_at': datetime.now(timezone.utc).isoformat()
        }
        
        producer.produce(
            topic,
            key=str(record['stay_id']),
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
    print("Patient Vitals Producer - BIGQUERY CONTINUOUS MODE")
    print("=" * 60)
    
    producer = create_producer()
    print(f"✓ Connected to Confluent Cloud")
    
    # Load data from BigQuery (once, then loop)
    vitals_list = load_vitals_from_bigquery()
    
    loop_count = 0
    
    while True:
        loop_count += 1
        print(f"\n🔄 Starting loop #{loop_count}...")
        
        try:
            count = produce_vitals(producer, vitals_list)
            print(f"✓ Completed loop #{loop_count}: sent {count} records")
        except Exception as e:
            print(f"❌ Error in loop #{loop_count}: {e}")
        
        print("⏳ Waiting 10 seconds before next loop...")
        time.sleep(10)


if __name__ == "__main__":
    main()
