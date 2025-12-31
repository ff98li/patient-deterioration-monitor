# Production Deployment Guide

## Overview

This guide deploys the Patient Deterioration Monitor to Google Cloud Platform:
- **GCE VM**: Runs Kafka producers, consumer, and Flask API
- **Cloud Run**: Serves the React dashboard (alternative: Firebase Hosting)
- **Confluent Cloud**: Kafka streaming (already set up)

**Live URLs (after deployment):**
- Dashboard: `https://icu.ffli.dev`
- API: `https://patient-deterioration-monitor.ffli.dev`

---

## Part 1: GCE VM Setup

### 1.1 Create the VM

```bash
# Set your preferred zone (use consistently throughout)
export GCP_ZONE="us-central1-a"

# Create VM instance
gcloud compute instances create patient-monitor-vm \
  --zone=$GCP_ZONE \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server \
  --scopes=cloud-platform

# Allow traffic on port 5050
gcloud compute firewall-rules create allow-api-5050 \
  --allow=tcp:5050 \
  --target-tags=http-server \
  --description="Allow Flask API traffic"
```

### 1.2 SSH into the VM

```bash
gcloud compute ssh patient-monitor-vm --zone=$GCP_ZONE
```

### 1.3 Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Create virtual environment (use python3.11 explicitly)
python3.11 -m venv venv
source venv/bin/activate

# Verify Python version
python --version  # Should show Python 3.11.x
```

### 1.4 Clone Project Repository

On the VM:
```bash
cd ~
git clone https://github.com/ff98li/patient-deterioration-monitor.git
```

### 1.5 Install Python Dependencies

```bash
cd ~/patient-deterioration-monitor
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 1.6 Set Up Google Cloud Credentials

For Vertex AI access, set up application default credentials on the VM:

```bash
# On the VM
gcloud auth application-default login
```

Or upload a service account key:
```bash
# From local machine
gcloud compute scp path/to/service-account-key.json patient-monitor-vm:~/patient-deterioration-monitor/ --zone=$GCP_ZONE

# On VM, set environment variable
echo 'export GOOGLE_APPLICATION_CREDENTIALS=~/patient-deterioration-monitor/service-account-key.json' >> ~/.bashrc
source ~/.bashrc
```

### 1.7 Set Up Config

Create `config.py` on the VM with your credentials:

Content:
```python
# Confluent Cloud
CONFLUENT_BOOTSTRAP_SERVER = "your-server.confluent.cloud:9092"
CONFLUENT_API_KEY = "your-api-key"
CONFLUENT_API_SECRET = "your-api-secret"

# Kafka Topics
KAFKA_VITALS_TOPIC = "patient-vitals"
KAFKA_LABS_TOPIC = "patient-labs"

# GCP
GCP_PROJECT_ID = "your-project-id"
GCP_REGION = "us-central1"

# Vertex AI
VERTEX_AI_MODEL = "gemini-2.5-flash"

# Alert settings
ALERT_THRESHOLD = 3

# API settings
API_HOST = "0.0.0.0"
API_PORT = 5050
```

### 1.9 Test the Setup

```bash
cd ~/patient-deterioration-monitor
source venv/bin/activate

# Test API starts
python run_combined.py &

# Test from another terminal (or use curl in same terminal after Ctrl+C)
curl http://localhost:5050/

# Stop the test
pkill -f run_combined.py
```

# Part 2: Run Backend Services (Revised)

## Using Screen Sessions

### 2.1 Install Screen (if not already installed)

```bash
sudo apt install -y screen
```

### 2.2 Start API + Consumer

```bash
# Create a new screen session
screen -S api

# Inside the screen session
cd ~/patient-deterioration-monitor
source venv/bin/activate
python run_combined.py

# Detach from screen: press Ctrl+A, then D
```

### 2.3 Start Vitals Producer

```bash
# Create a new screen session
screen -S vitals

# Inside the screen session
cd ~/patient-deterioration-monitor
source venv/bin/activate
python vitals_producer_continuous.py

# Detach from screen: press Ctrl+A, then D
```

### 2.4 Start Labs Producer

```bash
# Create a new screen session
screen -S labs

# Inside the screen session
cd ~/patient-deterioration-monitor
source venv/bin/activate
python lab_producer_continuous.py

# Detach from screen: press Ctrl+A, then D
```

### 2.5 Screen Quick Reference

```bash
# List all screen sessions
screen -ls

# Reattach to a session
screen -r api
screen -r vitals
screen -r labs

# Detach from inside a session
# Press Ctrl+A, then D

# Kill a session (from inside)
# Press Ctrl+C to stop script, then type 'exit'
```

### 2.6 Get VM External IP

```bash
gcloud compute instances describe patient-monitor-vm \
  --zone=$GCP_ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Test API externally:
```bash
curl http://EXTERNAL_IP:5050/
```

## Part 3: Deploy React Dashboard

#### 3.1 Update API URL

In your local dashboard folder, create `.env.production`:
```bash
VITE_API_URL=https://patient-deterioration-monitor.ffli.dev
```

#### 3.2 Build Docker Image

```bash
cd ~/patient-deterioration-monitor/dashboard

# Build the image
docker build -t gcr.io/YOUR_PROJECT_ID/patient-monitor-dashboard .

# Push to Container Registry
docker push gcr.io/YOUR_PROJECT_ID/patient-monitor-dashboard
```

#### 3.3 Deploy to Cloud Run

```bash
gcloud run deploy patient-monitor-dashboard \
  --image gcr.io/YOUR_PROJECT_ID/patient-monitor-dashboard \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## Part 4: Set Up Custom Domain (Optional)

### 4.1 API Domain with GCP Load Balancer

For HTTPS on the API, set up a load balancer with managed SSL:

```bash
# Reserve static IP
gcloud compute addresses create patient-monitor-api-ip --global

# Create health check
gcloud compute health-checks create http patient-monitor-health \
  --port=5050 \
  --request-path=/

# Create backend service
gcloud compute backend-services create patient-monitor-backend \
  --protocol=HTTP \
  --port-name=http \
  --health-checks=patient-monitor-health \
  --global

# Create URL map
gcloud compute url-maps create patient-monitor-lb \
  --default-service=patient-monitor-backend

# Create SSL certificate
gcloud compute ssl-certificates create patient-monitor-cert \
  --domains=patient-deterioration-monitor.ffli.dev \
  --global

# Create HTTPS proxy
gcloud compute target-https-proxies create patient-monitor-https-proxy \
  --url-map=patient-monitor-lb \
  --ssl-certificates=patient-monitor-cert

# Create forwarding rule
gcloud compute forwarding-rules create patient-monitor-https-rule \
  --address=patient-monitor-api-ip \
  --global \
  --target-https-proxy=patient-monitor-https-proxy \
  --ports=443
```

### 4.2 Dashboard Domain

For Cloud Run, map your custom domain in the Cloud Console under Cloud Run > Manage Custom Domains.

---

## Part 5: Verify Everything Works

### Checklist

- [ ] VM is running: `gcloud compute instances list`
- [ ] All services running: `sudo systemctl status patient-monitor-*`
- [ ] API health check: `curl http://EXTERNAL_IP:5050/`
- [ ] Patients endpoint: `curl http://EXTERNAL_IP:5050/api/patients`
- [ ] Dashboard loads in browser
- [ ] Dashboard shows real patient data (not demo mode)
- [ ] Risk level filter works
- [ ] Confidence filter works
- [ ] Patient detail modal opens
- [ ] AI assessment displays
- [ ] Alert feed shows events
- [ ] Confluent console shows messages flowing

---

## Troubleshooting


### CORS errors in browser
Update `dashboard_api.py` to allow your domain:
```python
CORS(app, origins=[
    'http://localhost:5173',
    'http://localhost:3000',
    'https://icu.ffli.dev',
    'https://your-project-id.web.app',
    'https://your-project-id.firebaseapp.com'
])
```
