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

-- Use same 500 patients as vitals
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
    -- Filter outliers
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