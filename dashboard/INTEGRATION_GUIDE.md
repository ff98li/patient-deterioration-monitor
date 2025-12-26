# Dashboard Integration Guide

This guide explains how to integrate the React dashboard with the real-time backend pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Vitals     │     │    Labs      │     │   Consumer   │    │
│  │   Producer   │────►│   Producer   │────►│  Multistream │    │
│  └──────────────┘     └──────────────┘     └──────┬───────┘    │
│                                                   │             │
│                        Confluent Kafka            │             │
│                                                   │             │
│                                                   ▼             │
│                                            ┌──────────────┐     │
│                                            │ shared_state │     │
│                                            └──────┬───────┘     │
│                                                   │             │
│                                                   ▼             │
│  ┌──────────────┐                         ┌──────────────┐     │
│  │    React     │◄───── HTTP/JSON ───────►│  Flask API   │     │
│  │  Dashboard   │                         │  (port 5050) │     │
│  │ (port 5173)  │                         └──────────────┘     │
│  └──────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
patient-monitoring/
├── data/
│   ├── patient_vitals.csv
│   └── patient_labs.csv
├── config.py                    # Kafka & GCP credentials
├── producer.py                  # Vitals producer
├── lab_producer.py              # Labs producer  
├── consumer_multistream.py      # Multi-stream consumer (updated)
├── model.py                     # MEWS & AI interpretation
├── lab_analysis.py              # Lab analysis
├── shared_state.py              # Shared state (updated)
├── dashboard_api.py             # Flask API (new)
└── dashboard/                   # React frontend
    ├── src/
    │   ├── App.tsx
    │   ├── services/
    │   │   ├── apiService.ts    # Real API calls
    │   │   └── mockDataService.ts
    │   └── components/
    ├── package.json
    └── .env.local
```

## Setup Instructions

### Step 1: Copy Backend Files

Copy the new backend files to your project:

```bash
cd ~/patient-monitoring

# Copy updated shared_state.py (backup old one first)
cp shared_state.py shared_state.py.old
cp /path/to/new/shared_state.py .

# Copy new dashboard API
cp /path/to/new/dashboard_api.py .
```

### Step 2: Install Backend Dependencies

```bash
pip install flask flask-cors --break-system-packages
```

### Step 3: Update consumer_multistream.py

The consumer needs to call the new shared_state functions. Key changes:

```python
# After getting AI interpretation, update shared state:
shared_state.update_patient_ai(stay_id, ai_result)

# After checking alert confirmation:
shared_state.update_patient_alert_status(
    stay_id, 
    confirmation['status'] == 'CONFIRMED',
    pending_alerts[stay_id]['trigger_count']
)
```

### Step 4: Set Up React Frontend

```bash
cd ~/patient-monitoring

# Copy dashboard folder
cp -r /path/to/dashboard ./dashboard

cd dashboard

# Install dependencies
npm install

# Create environment file
cp .env.example .env.local
# Edit .env.local if needed (default: http://localhost:5050)
```

### Step 5: Run the System

Open **5 terminals**:

```bash
# Terminal 1: Flask API
cd ~/patient-monitoring
python dashboard_api.py

# Terminal 2: Consumer
python consumer_multistream.py

# Terminal 3: Vitals Producer
python producer.py

# Terminal 4: Labs Producer  
python lab_producer.py

# Terminal 5: React Dashboard
cd dashboard
npm run dev
```

### Step 6: Access Dashboard

Open browser to: **http://localhost:5173**

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/data` | GET | All dashboard data (patients, alerts, stats) |
| `/api/patients` | GET | All patients sorted by risk |
| `/api/patients/<id>` | GET | Single patient details |
| `/api/patients/<id>/history` | GET | Patient trend history |
| `/api/alerts` | GET | All alerts |
| `/api/alerts/<id>/acknowledge` | POST | Acknowledge an alert |
| `/api/stats` | GET | Dashboard statistics |

## Data Format

The API returns data in this format:

```json
{
  "patients": [
    {
      "stay_id": 30001446,
      "subject_id": 10001234,
      "mews_score": 5,
      "risk_level": "HIGH",
      "vitals": {
        "heart_rate": 125,
        "respiratory_rate": 28,
        "spo2": 91,
        "systolic_bp": 95,
        "diastolic_bp": 60,
        "temperature_f": 101.2
      },
      "labs": {
        "lactate": 2.4,
        "creatinine": 1.8,
        "wbc": 14.2,
        "potassium": 3.2
      },
      "labs_age_minutes": 120,
      "sepsis_risk": "MODERATE",
      "ai_confidence": "MEDIUM",
      "ai_assessment": "WARNING: Hemodynamic instability...",
      "ai_recommendation": "Continuous monitoring...",
      "confidence_reasoning": "Most vitals present...",
      "trend_confirmed": true,
      "consecutive_readings": 2,
      "last_updated": "2025-01-05T10:30:00Z"
    }
  ],
  "alerts": [...],
  "stats": {
    "total_patients": 500,
    "critical_count": 2,
    "high_count": 15,
    "alerts_today": 47,
    "stream_status": "active",
    "last_vitals_received": "2025-01-05T10:30:02Z"
  }
}
```

## Demo Mode

If the backend is unavailable, the dashboard automatically falls back to **Demo Mode** using mock data. This is useful for:

- Testing the UI without running the full pipeline
- Presentations where you can't run Kafka
- Development of frontend features

A yellow banner shows when running in demo mode.

## Troubleshooting

### Dashboard shows "Demo Mode"

- Check if Flask API is running on port 5050
- Check browser console for CORS errors
- Verify `.env.local` has correct API URL

### No patients showing

- Check if consumer_multistream.py is running
- Check if producers are sending data
- Check Confluent Cloud for topic activity

### CORS Errors

The Flask API has CORS enabled for localhost. If deploying, update the `CORS()` configuration in `dashboard_api.py`.

## Production Deployment

For Cloud Run deployment, see the separate deployment guide. Key points:

1. Build React app: `npm run build`
2. Serve static files from Flask or separate CDN
3. Set `VITE_API_URL` to Cloud Run API URL
4. Configure CORS for production domain
