# Real-Time Patient Deterioration Prediction System
**AI Partner Catalyst: Confluent Challenge**

*A real-time clinical decision support system for critical care that predicts patient deterioration using real-time streaming vital signs and laboratory data, powered by Confluent Cloud, Apache Kafka and Google Cloud Vertex AI.*

## Project Overview
This project addresses the critical "failure to rescue" gap in modern inpatient care. Despite the abundance of physiological data in hospitals, In-Hospital Cardiac Arrest (IHCA) remains a leading cause of preventable mortality. This system transitions monitoring from reactive, batch-based analysis to a Real-Time, Multimodal Streaming Intelligence platform capable of detecting patient deterioration hours before a critical event.

## Background & Clinical Rationale
### The "80%" Reality
Current clinical literature establishes that cardiac arrest is rarely a sudden, unpredictable event. Research consistently demonstrates that 80% of in-hospital cardiac arrests are preceded by identifiable physiological warning signs, known as clinical antecedents (Schein et al., 1990). These signs typically manifest as progressive instability in respiratory rate, heart rate, or blood pressure, often occurring alongside subtle changes in mental status (Hillman et al., 2001).

### The 6-8 Hour Window
Crucially, these warning signs are detectable for an average of 6 to 8 hours prior to the terminal event (Schein et al., 1990; Hillman et al., 2001). This creates a significant "window of opportunity" for early intervention. However, traditional intermittent nursing checks (typically every 4-8 hours) frequently miss this window, leading to reactive "Code Blue" responses rather than proactive care (Kwon et al., 2018).

### Economic Impact
The cost of missing this window is severe. Intensive Care Unit (ICU) transfers triggered by late-stage deterioration are significantly more expensive than early interventions delivered on the ward. Studies indicate that the direct costs per day for ICU survivors can be 6 to 7 times higher than for non-ICU care (Hamilton et al., 1995). Furthermore, complications arising from delayed detection, such as Acute Kidney Injury (AKI) or hospital-acquired infections, can increase mortality risk by 3-5 times and add substantially to the cost per episode (Observe Medical, 2021). By preventing unplanned ICU admissions, this system aims to reduce length of stay and alleviate capacity constraints ("bed blocking").

## System Goals
1. **Ingest High-Velocity Data:** Handle continuous waveforms (ECG, PPG) at scale, moving beyond static tabular vitals (Omer, 2025).

2. **Reduce Latency:** Shift from batch processing (which can incur 12-24h delays) to stream processing (<1s latency) to capture rapid deterioration within the actionable window (Omer, 2025).

3. **Minimize False Alarms:** Utilize Multimodal AI (Waveforms + Clinical Text + Vitals) to improve specificity and reduce alert fatigue, a critical failure point of previous generation systems (Kwon et al., 2018).




---

## Problem Statement

### The Challenge: Preventable In-Hospital Deterioration

- **80% of cardiac arrests** show warning signs 6-8 hours before the event
- **Each hour of delayed intervention** increases ICU mortality by 1.5%
- **Alert fatigue** plagues existing systems — PPV as low as 6% means 94 false alarms per 6 true alerts
- **ICU costs 2.8x more** than ward care ($4,186/day vs $1,492/day)

### Our Solution

A streaming analytics platform that:
1. Ingests real-time vital signs and lab results via Confluent Kafka
2. Calculates validated clinical scores (MEWS) in real-time
3. Uses Vertex AI Gemini for zero-shot clinical interpretation
4. Reduces false alarms through trend-based alert confirmation
5. Provides confidence-aware AI assessments

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                    │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  Vital Signs    │    │  Lab Results    │    │  [Future]       │          │
│  │  (MIMIC-IV)     │    │  (MIMIC-IV)     │    │  Chest X-rays   │          │
│  └────────┬────────┘    └────────┬────────┘    └─────────────────┘          │
└───────────┼──────────────────────┼──────────────────────────────────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONFLUENT KAFKA                                      │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │ patient-vitals  │    │  patient-labs   │                                 │
│  │     topic       │    │     topic       │                                 │
│  └────────┬────────┘    └────────┬────────┘                                 │
│           │                      │                                          │
│           └──────────┬───────────┘                                          │
│                      │                                                      │
│              ┌───────▼───────┐                                              │
│              │ Multi-Stream  │  ← Stream JOIN by patient (stay_id)          │
│              │   Consumer    │  ← Temporal alignment & staleness detection  │
│              └───────┬───────┘                                              │
└──────────────────────┼──────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PROCESSING & ANALYSIS                                   │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  MEWS Score     │    │  Lab Analysis   │    │ Sepsis Screening│          │
│  │  Calculator     │    │  Engine         │    │ Cross-correlation│         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘          │
│           │                      │                      │                   │
│           └──────────────────────┼──────────────────────┘                   │
│                                  │                                          │
│                      ┌───────────▼───────────┐                              │
│                      │  Alert Confirmation   │                              │
│                      │  (Trend-based)        │                              │
│                      └───────────┬───────────┘                              │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      VERTEX AI (Gemini 2.5 Flash)                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │  Zero-Shot Clinical Interpretation                          │            │
│  │  • Confidence-aware assessment (LOW/MEDIUM/HIGH)            │            │
│  │  • Priority concerns identification                         │            │
│  │  • Recommended actions                                      │            │
│  │  • Uncertainty quantification                               │            │
│  └─────────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OUTPUT                                            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  Real-time      │    │  REST API       │    │  Alert System   │          │
│  │  Dashboard      │    │  (Flask)        │    │  (Confirmed)    │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Multi-Stream Processing with Confluent Kafka

| Confluent Feature | Implementation |
|-------------------|----------------|
| **Multi-topic consumption** | Simultaneous vitals + labs streams |
| **Stream join by key** | Patient data combined by `stay_id` |
| **Temporal windowing** | Lab staleness detection (>4hr threshold) |
| **Real-time enrichment** | Sepsis screening across data streams |

### 2. Clinical Scoring (MEWS)

Modified Early Warning Score calculation with risk stratification:

| MEWS Score | Risk Level | Response |
|------------|------------|----------|
| 0-1 | LOW | Routine monitoring |
| 2-3 | MEDIUM | Increased observation |
| 4-5 | HIGH | Urgent clinical review |
| ≥6 | CRITICAL | Immediate intervention |

### 3. Zero-Shot LLM Advantage

**Key Differentiator**: No training data required.

- Leverages Gemini's pre-existing medical knowledge
- Interpretable natural language outputs
- Faster deployment than traditional ML pipelines
- More generalizable across patient populations

### 4. Confidence-Aware AI Assessment

```
AI Assessment (Confidence: 🟡 MEDIUM):
  The patient presents with severe hypotension and multi-organ 
  dysfunction, including acute kidney injury...
  
  📋 Concerns: Hypotensive shock, Severe anemia, AKI
  💊 Actions: Urgent medical evaluation, Stat repeat labs
  
  ⚠️ While vital sign data is incomplete (3/7) and lab results 
  are ~24 hours old, the combined picture strongly indicates 
  a critical clinical scenario.
```

### 5. Alert Fatigue Mitigation

**Problem**: Traditional systems have PPV as low as 6%

**Our Solution**: Trend-based confirmation
- Require 2+ consecutive elevated readings within 5 minutes
- Prevents false alarms from transient spikes
- Maintains sensitivity while improving specificity

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| **Streaming Platform** | Confluent Kafka (Cloud) |
| **AI/ML** | Google Vertex AI (Gemini 2.5 Flash) |
| **Data Source** | MIMIC-IV (BigQuery) |
| **Backend** | Python, Flask |
| **Dashboard** | HTML/JS (real-time updates) |
| **Cloud** | Google Cloud Platform |

---

## Data Pipeline

### Vital Signs (266K records, 500 patients)
- Heart Rate, Respiratory Rate, SpO2
- Systolic BP, Diastolic BP, MAP
- Temperature

### Laboratory Results (25K records)
- Lactate (sepsis marker)
- Creatinine (kidney function)
- WBC (infection indicator)
- Hemoglobin, Platelets
- Electrolytes (K, Na, Cl, HCO3)
- Glucose

### Measurement Frequency (Real ICU Patterns)
| Vital | Frequency | Method |
|-------|-----------|--------|
| HR, SpO2 | Continuous | Bedside monitor |
| Respiratory Rate | Frequent | Monitor/manual |
| Blood Pressure | 15-60 min | Cuff/arterial line |
| Temperature | 2-4 hours | Manual |

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Confluent Cloud account
- Google Cloud account with Vertex AI enabled
- MIMIC-IV BigQuery access (PhysioNet credentialing)

### Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd patient-monitoring

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp config.example.py config.py
# Edit config.py with your credentials
```

### Configuration (config.py)

```python
# Confluent Kafka
CONFLUENT_BOOTSTRAP_SERVER = "your-cluster.confluent.cloud:9092"
CONFLUENT_API_KEY = "your-api-key"
CONFLUENT_API_SECRET = "your-api-secret"

# Google Cloud
GCP_PROJECT_ID = "your-project-id"
GCP_REGION = "us-central1"

# Thresholds
ALERT_THRESHOLD = 4
KAFKA_TOPIC = "patient-vitals"
```

### Running the System

```bash
# Terminal 1: Dashboard
python dashboard.py

# Terminal 2: Multi-stream Consumer
python consumer_multistream.py

# Terminal 3: Vitals Producer
python producer.py

# Terminal 4: Labs Producer
python lab_producer.py
```

Access dashboard at: `http://localhost:5050`

---

## Project Structure

```
patient-monitoring/
├── config.py                 # Configuration & credentials
├── producer.py               # Vital signs Kafka producer
├── lab_producer.py           # Lab results Kafka producer
├── consumer.py               # Single-stream consumer
├── consumer_multistream.py   # Multi-stream consumer (vitals + labs)
├── model.py                  # MEWS calculation & AI interpretation
├── lab_analysis.py           # Lab analysis & sepsis screening
├── dashboard.py              # Flask web dashboard
├── shared_state.py           # Shared state management
├── data/
│   ├── patient_vitals.csv    # 266K vital sign records
│   └── patient_labs.csv      # 25K lab result records
└── requirements.txt
```

---

## Clinical Validation

### MEWS Scoring
Based on validated Modified Early Warning Score:
- Subbe et al. (2001) - Original MEWS validation
- Demonstrated correlation with cardiac arrest, ICU admission, mortality

### Sepsis Screening
Cross-correlates vitals and labs for sepsis indicators:
- Elevated lactate (>2 mmol/L)
- WBC abnormality (<4 or >12 K/uL)
- Tachycardia, tachypnea, hypotension
- Thrombocytopenia

### Literature Support
- Schein et al. (1990): 84% of arrests have warning signs 8hrs before
- Young et al. (2003): ≥4hr intervention delay = 3.5x mortality
- Kyeremanteng et al. (2018): ICU costs 2.8x ward costs

---

## Future Enhancements

1. **MIMIC-CXR Integration**: Chest X-ray analysis for respiratory deterioration
2. **Nursing Notes**: Unstructured text analysis for subtle clinical cues
3. **ECG Morphology**: QT interval, ST elevation detection
4. **Federated Learning**: Multi-hospital deployment without data sharing
5. **Alert Acknowledgment**: Clinician feedback loop for continuous improvement

---

## Acknowledgments

- MIMIC-IV dataset (PhysioNet)
- Confluent for streaming infrastructure
- Google Cloud for Vertex AI platform

---

# References
Hamilton, S., et al. (1995). ICU and non-ICU cost per day. Canadian Journal of Anaesthesia, 42(3), 192–196.

Hillman, K., et al. (2001). Redefining in-hospital resuscitation: the concept of the medical emergency team. Resuscitation, 48(2), 105–110.

Johnson, A.E.W., et al. (2023). MIMIC-IV, a freely accessible electronic health record dataset. Sci Data 10, 1.

Kwon, J. M., et al. (2018). An Algorithm Based on Deep Learning for Predicting In-Hospital Cardiac Arrest. Journal of the American Heart Association, 7(13), e008678.

Observe Medical ASA. (2021). Third quarter 2021 presentation. Retrieved from Observe Medical Investor Relations.

Omer, R. (2025). Real-Time & Streaming Analytics in Healthcare: Use Cases & Architecture. Embarking on Voyage.

Schein, R. M., et al. (1990). Clinical antecedents to in-hospital cardiopulmonary arrest. Chest, 98(6), 1388–1392.


## License

MIT License

Copyright (c) 2025 Feifei

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.