WITH vital_mappings AS (
  SELECT *
  FROM UNNEST([
    STRUCT(220045 AS itemid, 'heart_rate' AS vital_type),
    STRUCT(220050 AS itemid, 'systolic_bp' AS vital_type),
    STRUCT(220051 AS itemid, 'diastolic_bp' AS vital_type),
    STRUCT(220052 AS itemid, 'mean_arterial_pressure' AS vital_type),
    STRUCT(220179 AS itemid, 'systolic_bp' AS vital_type),      -- Non-invasive
    STRUCT(220180 AS itemid, 'diastolic_bp' AS vital_type),      -- Non-invasive
    STRUCT(220181 AS itemid, 'mean_arterial_pressure' AS vital_type), -- Non-invasive
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
  LIMIT 500  -- Expand to 500 patients
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
    -- Filter out obvious outliers
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