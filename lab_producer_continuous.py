"""
Continuous Labs Producer - BigQuery Version

Streams lab results directly from MIMIC-IV BigQuery dataset to Confluent Kafka.
Loops forever for continuous demo.

Uses the same SQL logic as patient_labs_500.sql
"""

import json
import time
from datetime import datetime, timezone
from confluent_kafka import Producer
from google.cloud import bigquery
from collections import defaultdict

import config


# BigQuery SQL matching patient_labs_500.sql exactly
LABS_QUERY = """
WITH lab_mappings AS (
  SELECT *
  FROM UNNEST([
    STRUCT(50813 AS itemid, 'lactate' AS lab_type, 'mmol/L' AS unit),
    STRUCT(50912 AS itemid, 'creatinine' AS lab_type, 'mg/dL' AS unit),
    STRUCT(50971 AS itemid, 'potassium' AS lab_type, 'mEq/L' AS unit),
    STRUCT(51301 AS itemid, 'wbc' AS lab_type, 'K/uL' AS unit),
    STRUCT(51222 AS itemid, 'hemoglobin' AS lab_type, 'g/dL' AS unit),
    STRUCT(51265 AS itemid, 'platelet' AS lab_type, 'K/uL' AS unit),
    STRUCT(50882 AS itemid, 'bicarbonate' AS lab_type, 'mEq/L' AS unit),
    STRUCT(50902 AS itemid, 'chloride' AS lab_type, 'mEq/L' AS unit),
    STRUCT(50931 AS itemid, 'glucose' AS lab_type, 'mg/dL' AS unit),
    STRUCT(50983 AS itemid, 'sodium' AS lab_type, 'mEq/L' AS unit)
  ])
),

sample_stays AS (
  SELECT DISTINCT stay_id
  FROM `physionet-data.mimiciv_3_1_icu.icustays`
  ORDER BY stay_id
  LIMIT 500
),

labs AS (
  SELECT 
    ie.subject_id,
    ie.stay_id,
    le.charttime,
    lm.lab_type,
    le.valuenum AS lab_value,
    lm.unit
  FROM `physionet-data.mimiciv_3_1_hosp.labevents` le
  INNER JOIN `physionet-data.mimiciv_3_1_icu.icustays` ie 
    ON le.subject_id = ie.subject_id
    AND le.charttime BETWEEN ie.intime AND ie.outtime
  INNER JOIN sample_stays ss ON ie.stay_id = ss.stay_id
  INNER JOIN lab_mappings lm ON le.itemid = lm.itemid
  WHERE le.valuenum IS NOT NULL
    AND le.valuenum > 0
    AND (
      (lm.lab_type = 'lactate' AND le.valuenum BETWEEN 0.1 AND 30) OR
      (lm.lab_type = 'creatinine' AND le.valuenum BETWEEN 0.1 AND 25) OR
      (lm.lab_type = 'potassium' AND le.valuenum BETWEEN 1.5 AND 10) OR
      (lm.lab_type = 'wbc' AND le.valuenum BETWEEN 0.1 AND 100) OR
      (lm.lab_type = 'hemoglobin' AND le.valuenum BETWEEN 3 AND 20) OR
      (lm.lab_type = 'platelet' AND le.valuenum BETWEEN 5 AND 1000) OR
      (lm.lab_type = 'bicarbonate' AND le.valuenum BETWEEN 5 AND 50) OR
      (lm.lab_type = 'chloride' AND le.valuenum BETWEEN 70 AND 140) OR
      (lm.lab_type = 'glucose' AND le.valuenum BETWEEN 20 AND 1000) OR
      (lm.lab_type = 'sodium' AND le.valuenum BETWEEN 110 AND 180)
    )
)

SELECT 
  subject_id,
  stay_id,
  charttime,
  lab_type,
  lab_value,
  unit
FROM labs
ORDER BY stay_id, charttime, lab_type
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
        'client.id': 'patient-labs-producer'
    }
    return Producer(conf)


def load_labs_from_bigquery():
    """Load labs data from BigQuery and group by (stay_id, charttime)."""
    
    client = bigquery.Client(project=config.GCP_PROJECT_ID)
    
    print("📊 Querying MIMIC-IV Labs from BigQuery...")
    print("   (This may take 10-30 seconds for initial query)")
    
    query_job = client.query(LABS_QUERY)
    results = query_job.result()
    
    # Group by (stay_id, charttime) like the CSV version
    labs_by_time = defaultdict(lambda: {
        'subject_id': None,
        'stay_id': None,
        'charttime': None,
        'labs': {},
        'units': {},
    })
    
    row_count = 0
    unique_patients = set()
    
    for row in results:
        key = (row.stay_id, row.charttime)
        labs_by_time[key]['subject_id'] = row.subject_id
        labs_by_time[key]['stay_id'] = row.stay_id
        labs_by_time[key]['charttime'] = row.charttime
        
        lab_type = row.lab_type
        lab_value = row.lab_value
        unit = row.unit
        
        if lab_type and lab_value is not None:
            labs_by_time[key]['labs'][lab_type] = round(float(lab_value), 2)
            labs_by_time[key]['units'][lab_type] = unit if unit else ''
        
        unique_patients.add(row.stay_id)
        row_count += 1
    
    # Convert to list and sort
    labs_list = list(labs_by_time.values())
    labs_list.sort(key=lambda x: (x['stay_id'], x['charttime'] or datetime.min))
    
    print(f"✓ Loaded {row_count} lab records")
    print(f"✓ Unique patients: {len(unique_patients)}")
    print(f"✓ Grouped into {len(labs_list)} timestamp groups")
    
    return labs_list


def produce_labs(producer, labs_list, topic='patient-labs', delay=0.1):
    """Stream labs data to Kafka, matching CSV producer format."""
    
    count = 0
    
    for record in labs_list:
        labs = record['labs']
        units = record['units']
        
        if not labs:
            continue
        
        # Match the CSV producer message format exactly
        message = {
            'subject_id': int(record['subject_id']) if record['subject_id'] else 0,
            'stay_id': int(record['stay_id']),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'labs': labs,
            'units': units,
            'produced_at': datetime.now(timezone.utc).isoformat()
        }
        
        producer.produce(
            topic,
            key=str(record['stay_id']),
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
    print("Patient Labs Producer - BIGQUERY CONTINUOUS MODE")
    print("=" * 60)
    
    producer = create_producer()
    print(f"✓ Connected to Confluent Cloud")
    
    # Load data from BigQuery (once, then loop)
    labs_list = load_labs_from_bigquery()
    
    loop_count = 0
    
    while True:
        loop_count += 1
        print(f"\n🔄 Starting loop #{loop_count}...")
        
        try:
            count = produce_labs(producer, labs_list)
            print(f"✓ Completed loop #{loop_count}: sent {count} records")
        except Exception as e:
            print(f"❌ Error in loop #{loop_count}: {e}")
        
        print("⏳ Waiting 10 seconds before next loop...")
        time.sleep(10)


if __name__ == "__main__":
    main()
