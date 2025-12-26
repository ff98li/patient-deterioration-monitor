# System Architecture Documentation

## Architectural Paradigm: Kappa Architecture
To meet the requirement of analyzing high-throughput ICU data in real-time, this system abandons the traditional Lambda Architecture (which separates batch and speed layers) in favor of a Kappa Architecture. In this model, the data stream is the single source of truth, enabling low-latency processing and eliminating "training-serving skew" (Omer, 2025).

## Core Components
1. Data Ingestion Layer (The Nervous System)
Technology: Apache Kafka

Function: Acts as a high-throughput distributed log to ingest "firehose" data from bedside monitors (Waveforms @ 250-500Hz) and EHR updates (Labs, ADT events).

Rationale: Traditional databases cannot handle the write velocity of continuous waveform data. Kafka ensures durability and allows for data "replay" for model retraining (Omer, 2025).

2. Stream Processing Engine (The Brain)
Technology: Apache Flink

Function: Performs stateful stream processing.

Windowing: Maintains sliding windows (e.g., 15-minute tumbling windows) to calculate trends like heart rate variability or blood pressure slope.

Complex Event Processing (CEP): Detects patterns across multiple signals (e.g., hypotension + tachycardia) in milliseconds.

Differentiation: Unlike Spark Streaming (micro-batches), Flink provides true event-at-a-time processing, which is critical for sub-second alert latency.

3. Intelligence Layer (Multimodal AI)
Model Architecture: Hybrid Late Fusion Neural Network.

Input A (Time-Series): 1D-CNN or Transformer processing continuous vital sign trends and ECG waveforms (Kwon et al., 2018).

Input B (Unstructured Text): BERT-based LLM processing nursing notes and physician progress notes.

Fusion: Concatenates embeddings from both networks to output a risk score.

Explainability (XAI): Integrated SHAP (SHapley Additive exPlanations) values to provide clinicians with the "why" behind the alert (e.g., "Risk driven by rising Lactate and dropping SpO2").

4. Action Layer
Output: FHIR-compatible alerts sent to mobile devices for Rapid Response Teams (RRT).

Feedback Loop: Clinician responses (Acknowledged/Dismissed) are captured back into Kafka to fine-tune future model performance.


## Overview Diagram (Skeletal)

```
[MIMIC-IV BigQuery]
       │
       ├──► [patient_vitals.csv] ──► [producer.py] ──► [patient-vitals topic]
       │                                                        │
       └──► [patient_labs.csv] ──► [lab_producer.py] ──► [patient-labs topic]
                                                                │
                                                                ▼
                                                    [consumer_multistream.py]
                                                    ┌─────────────────────┐
                                                    │ • Stream JOIN       │
                                                    │ • MEWS Calculation  │
                                                    │ • Lab Analysis      │
                                                    │ • Sepsis Screening  │
                                                    │ • Alert Confirmation│
                                                    └──────────┬──────────┘
                                                               │
                                                               ▼
                                                    [Vertex AI Gemini 2.5]
                                                               │
                                                               ▼
                                                    [Dashboard + Alerts]
```

---

## Component Details

### 1. Data Ingestion Layer

#### Vitals Producer (producer.py)
```
Input:  patient_vitals.csv (266K records)
Output: patient-vitals Kafka topic

Message Schema:
{
  "subject_id": int,
  "stay_id": int,
  "timestamp": ISO8601,
  "vitals": {
    "heart_rate": float,
    "respiratory_rate": float,
    "spo2": float,
    "systolic_bp": float,
    "diastolic_bp": float,
    "mean_arterial_pressure": float,
    "temperature_f": float
  },
  "produced_at": ISO8601
}
```

#### Labs Producer (lab_producer.py)
```
Input:  patient_labs.csv (25K records)
Output: patient-labs Kafka topic

Message Schema:
{
  "subject_id": int,
  "stay_id": int,
  "timestamp": ISO8601,
  "labs": {
    "lactate": float,
    "creatinine": float,
    "potassium": float,
    "wbc": float,
    "hemoglobin": float,
    "platelet": float,
    "bicarbonate": float,
    "chloride": float,
    "glucose": float,
    "sodium": float
  },
  "units": {...},
  "produced_at": ISO8601
}
```

---

### 2. Confluent Kafka Layer

#### Topics Configuration

| Topic | Partitions | Purpose |
|-------|------------|---------|
| patient-vitals | 1 | Real-time vital signs |
| patient-labs | 6 | Laboratory results |

#### Key Design
- **Partition Key**: `stay_id` (ensures all data for a patient goes to same partition)
- **Enables**: Ordered processing per patient, efficient joins

---

### 3. Stream Processing Layer

#### Multi-Stream Consumer (consumer_multistream.py)

```
┌─────────────────────────────────────────────────────────┐
│                  STREAM JOIN LOGIC                       │
│                                                         │
│  patient-vitals ──┐                                     │
│                   ├──► JOIN by stay_id ──► Combined     │
│  patient-labs ────┘                        Analysis     │
│                                                         │
│  Join Type: Temporal (latest labs within 4hr window)    │
└─────────────────────────────────────────────────────────┘
```

#### Data Structures
```python
# In-memory state
patient_vitals_history: Dict[stay_id, List[vitals]]  # Last 50 per patient
patient_labs_history: Dict[stay_id, List[labs]]      # Last 20 per patient
patient_latest_labs: Dict[stay_id, labs]             # Most recent labs

# Alert tracking
pending_alerts: Dict[stay_id, {
    'first_triggered': datetime,
    'trigger_count': int,
    'last_mews': int,
    'confirmed': bool
}]
```

---

### 4. Clinical Analysis Layer

#### MEWS Calculation (model.py)

```
┌────────────────────────────────────────────────────────┐
│                   MEWS COMPONENTS                       │
├────────────────────────────────────────────────────────┤
│  Heart Rate        │  0-3 points based on ranges       │
│  Respiratory Rate  │  0-3 points based on ranges       │
│  Systolic BP       │  0-3 points based on ranges       │
│  Temperature       │  0-2 points based on ranges       │
│  SpO2              │  0-3 points based on ranges       │
├────────────────────────────────────────────────────────┤
│  Total Score       │  0-14 (higher = more critical)    │
└────────────────────────────────────────────────────────┘
```

#### Lab Analysis (lab_analysis.py)

```
┌────────────────────────────────────────────────────────┐
│              LAB REFERENCE RANGES                       │
├──────────────┬─────────────────────────────────────────┤
│ Lab Type     │ Critical Low │ Normal Range │ Critical High │
├──────────────┼──────────────┼──────────────┼───────────────┤
│ Lactate      │ -            │ 0.5-2.0      │ >4.0          │
│ Creatinine   │ -            │ 0.6-1.2      │ >4.0          │
│ Potassium    │ <2.5         │ 3.5-5.0      │ >6.5          │
│ WBC          │ <2.0         │ 4.0-11.0     │ >30.0         │
│ Hemoglobin   │ <6.0         │ 12.0-17.0    │ -             │
│ Platelet     │ <20          │ 150-400      │ -             │
└──────────────┴──────────────┴──────────────┴───────────────┘
```

#### Sepsis Screening

```
┌─────────────────────────────────────────────────────────┐
│               SEPSIS INDICATORS                          │
├─────────────────────────────────────────────────────────┤
│ FROM LABS:                                              │
│   • Lactate >2 mmol/L (+2), >4 mmol/L (+3)             │
│   • WBC <4 or >12 K/uL (+1)                            │
│   • Creatinine >2.0 mg/dL (+1)                         │
│   • Platelet <100 K/uL (+1)                            │
├─────────────────────────────────────────────────────────┤
│ FROM VITALS:                                            │
│   • Heart Rate >90 bpm (+1)                            │
│   • Respiratory Rate >20/min (+1)                      │
│   • Systolic BP <100 mmHg (+2)                         │
│   • Temperature >100.4°F or <96.8°F (+1)               │
├─────────────────────────────────────────────────────────┤
│ RISK LEVELS:                                            │
│   Score ≥5: HIGH    │ Score ≥3: MODERATE               │
│   Score ≥1: LOW     │ Score 0: MINIMAL                 │
└─────────────────────────────────────────────────────────┘
```

---

### 5. Alert Confirmation System

```
┌─────────────────────────────────────────────────────────┐
│            TREND-BASED ALERT CONFIRMATION                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Configuration:                                         │
│    ALERT_CONFIRMATION_COUNT = 2                         │
│    ALERT_CONFIRMATION_WINDOW_SECONDS = 300 (5 min)      │
│                                                         │
│  State Machine:                                         │
│                                                         │
│    NORMAL ──[elevated]──► PENDING (1/2)                 │
│       ▲                        │                        │
│       │                   [elevated within window]      │
│       │                        │                        │
│       │                        ▼                        │
│    [improved]              CONFIRMED ──► ALERT!         │
│       │                        │                        │
│       │                   [same episode]                │
│       │                        │                        │
│       └────────────────── ALREADY_ALERTED               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

### 6. AI Interpretation Layer

#### Vertex AI Integration

```
┌─────────────────────────────────────────────────────────┐
│              GEMINI 2.5 FLASH PROMPT                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  INPUT:                                                 │
│    • Vital signs with reference ranges                  │
│    • MEWS score and risk level                         │
│    • Lab results (if available, with age)              │
│    • Sepsis screening results                          │
│    • Data completeness metrics                         │
│                                                         │
│  OUTPUT (JSON):                                         │
│    {                                                    │
│      "interpretation": "2-3 sentence assessment",       │
│      "confidence": "LOW|MEDIUM|HIGH",                   │
│      "confidence_reasoning": "explanation",             │
│      "priority_concerns": ["list", "of", "concerns"],   │
│      "recommended_actions": ["list", "of", "actions"]   │
│    }                                                    │
│                                                         │
│  CONFIDENCE GUIDELINES:                                 │
│    HIGH: Complete vitals + recent labs, clear picture   │
│    MEDIUM: Most vitals, labs may be missing/stale       │
│    LOW: Missing key vitals, no labs, conflicting data   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

### 7. Output Layer

#### Dashboard (dashboard.py)

```
┌─────────────────────────────────────────────────────────┐
│                 FLASK DASHBOARD                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Endpoints:                                             │
│    GET /           → Main dashboard page                │
│    GET /api/data   → JSON: patients, alerts, stats      │
│                                                         │
│  Real-time Updates:                                     │
│    • JavaScript polling (1 second interval)             │
│    • Patient list with MEWS scores                      │
│    • Alert feed                                         │
│    • Statistics summary                                 │
│                                                         │
│  Data Source:                                           │
│    • shared_state.py (thread-safe in-memory state)      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Data Flow Sequence

```
1. [BigQuery] ──export──► [CSV files]

2. [producer.py] reads CSV ──► sends to [patient-vitals] topic
   [lab_producer.py] reads CSV ──► sends to [patient-labs] topic

3. [consumer_multistream.py] subscribes to BOTH topics
   │
   ├── On vitals message:
   │   ├── Calculate MEWS score
   │   ├── Look up latest labs for this patient (JOIN)
   │   ├── Check lab staleness (<4hr threshold)
   │   ├── Run sepsis screening (if labs available)
   │   ├── Determine combined risk level
   │   ├── Check alert confirmation (trend-based)
   │   └── If confirmed HIGH/CRITICAL:
   │       ├── Call Vertex AI for interpretation
   │       └── Display alert with AI assessment
   │
   └── On labs message:
       ├── Analyze against reference ranges
       ├── Update patient_latest_labs
       └── Display lab results with abnormal flags

4. [shared_state.py] maintains current state for dashboard

5. [dashboard.py] serves web UI with real-time updates
```

---

## Key Design Decisions

### Why Confluent Kafka?
1. **Decoupled producers/consumers**: Vitals and labs can scale independently
2. **Reliable delivery**: Critical for healthcare data
3. **Stream processing**: Real-time joins without batch delays
4. **Replay capability**: Re-process historical data for testing

### Why Zero-Shot LLM?
1. **No training data needed**: Deploy immediately
2. **Interpretable outputs**: Clinicians understand natural language
3. **Generalizable**: Works across patient populations
4. **Updatable**: Model improvements without retraining

### Why Trend-Based Confirmation?
1. **Reduces false alarms**: Prevents alert fatigue
2. **Maintains sensitivity**: True deterioration persists
3. **Configurable**: Adjust thresholds per clinical context
4. **Transparent**: Clear explanation of alert status

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Vitals throughput | ~3 KB/s |
| Labs throughput | ~8 KB/s |
| End-to-end latency | <2 seconds |
| AI interpretation | ~1-2 seconds |
| Dashboard refresh | 1 second |

---

## Scalability Considerations

### Current (Demo)
- Single consumer instance
- In-memory state
- 500 patients

### Production Path
- Consumer group with multiple instances
- Redis/PostgreSQL for state persistence
- Horizontal scaling via Kafka partitions
- Rate limiting for AI API calls

# References
* Kwon, J. M., et al. (2018). An Algorithm Based on Deep Learning for Predicting In-Hospital Cardiac Arrest. Journal of the American Heart Association, 7(13), e008678.

* Omer, R. (2025). Real-Time & Streaming Analytics in Healthcare: Use Cases & Architecture. Embarking on Voyage.

