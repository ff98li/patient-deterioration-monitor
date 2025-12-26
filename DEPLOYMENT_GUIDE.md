# Production Deployment Guide

## Overview

This guide deploys the Patient Deterioration Monitor to Google Cloud Platform:
- **GCE VM**: Runs Kafka producers, consumer, and Flask API
- **Firebase Hosting**: Serves the React dashboard
- **Confluent Cloud**: Kafka streaming (already set up)

---

## Part 1: GCE VM Setup

### 1.1 Create the VM

```bash
# Create VM instance
gcloud compute instances create patient-monitor-vm \
  --zone=us-central1-c \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server

# Allow traffic on port 5050
gcloud compute firewall-rules create allow-api-5050 \
  --allow=tcp:5050 \
  --target-tags=http-server \
  --description="Allow Flask API traffic"
```

### 1.2 SSH into the VM

```bash
gcloud compute ssh patient-monitor-vm --zone=us-central1-a
```

### 1.3 Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Create project directory
mkdir -p ~/patient-monitoring
cd ~/patient-monitoring

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 1.4 Upload Project Files

From your local machine:
```bash
# Zip the project
cd ~/patient-monitoring
zip -r patient-monitoring.zip . -x "venv/*" -x "__pycache__/*" -x "*.pyc" -x "dashboard/node_modules/*"

# Upload to VM
gcloud compute scp patient-monitoring.zip patient-monitor-vm:~/patient-monitoring/ --zone=us-central1-a
```

On the VM:
```bash
cd ~/patient-monitoring
unzip patient-monitoring.zip
```

### 1.5 Install Python Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 1.6 Upload Data Files

From your local machine:
```bash
# Upload data files
gcloud compute scp data/patient_vitals_500.csv patient-monitor-vm:~/patient-monitoring/data/ --zone=us-central1-a
gcloud compute scp data/patient_labs_500.csv patient-monitor-vm:~/patient-monitoring/data/ --zone=us-central1-a
```

### 1.7 Set Up Config

Create `config.py` on the VM with your credentials:
```python
# Confluent Cloud
CONFLUENT_BOOTSTRAP_SERVER = "your-server.confluent.cloud:9092"
CONFLUENT_API_KEY = "your-api-key"
CONFLUENT_API_SECRET = "your-api-secret"
KAFKA_TOPIC = "patient-vitals"

# GCP
GCP_PROJECT_ID = "your-project-id"
GCP_REGION = "us-central1"

# Alert settings
ALERT_THRESHOLD = 3
```

### 1.8 Test the Setup

```bash
# Test API starts
python run_combined.py &

# Test from another terminal
curl http://localhost:5050/
```

---

## Part 2: Run as Background Services

### 2.1 Create systemd Service for Combined Consumer + API

```bash
sudo nano /etc/systemd/system/patient-monitor-api.service
```

Content:
```ini
[Unit]
Description=Patient Monitor API and Consumer
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/patient-monitoring
Environment=PATH=/home/ubuntu/patient-monitoring/venv/bin
ExecStart=/home/ubuntu/patient-monitoring/venv/bin/python run_combined.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.2 Create Service for Vitals Producer

```bash
sudo nano /etc/systemd/system/patient-monitor-vitals.service
```

Content:
```ini
[Unit]
Description=Patient Monitor Vitals Producer
After=network.target patient-monitor-api.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/patient-monitoring
Environment=PATH=/home/ubuntu/patient-monitoring/venv/bin
ExecStart=/home/ubuntu/patient-monitoring/venv/bin/python producer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.3 Create Service for Labs Producer

```bash
sudo nano /etc/systemd/system/patient-monitor-labs.service
```

Content:
```ini
[Unit]
Description=Patient Monitor Labs Producer
After=network.target patient-monitor-api.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/patient-monitoring
Environment=PATH=/home/ubuntu/patient-monitoring/venv/bin
ExecStart=/home/ubuntu/patient-monitoring/venv/bin/python lab_producer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2.4 Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable patient-monitor-api
sudo systemctl enable patient-monitor-vitals
sudo systemctl enable patient-monitor-labs

# Start services
sudo systemctl start patient-monitor-api
sudo systemctl start patient-monitor-vitals
sudo systemctl start patient-monitor-labs

# Check status
sudo systemctl status patient-monitor-api
sudo systemctl status patient-monitor-vitals
sudo systemctl status patient-monitor-labs
```

### 2.5 View Logs

```bash
# API logs
sudo journalctl -u patient-monitor-api -f

# Vitals producer logs
sudo journalctl -u patient-monitor-vitals -f

# Labs producer logs
sudo journalctl -u patient-monitor-labs -f
```

### 2.6 Get VM External IP

```bash
gcloud compute instances describe patient-monitor-vm \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Test API externally:
```bash
curl http://EXTERNAL_IP:5050/api/data
```

---

## Part 3: Deploy React Dashboard

### 3.1 Update API URL

In your local dashboard folder, update `.env.local`:
```bash
VITE_API_URL=http://EXTERNAL_IP:5050
```

Or create `.env.production`:
```bash
VITE_API_URL=http://EXTERNAL_IP:5050
```

### 3.2 Build for Production

```bash
cd ~/patient-monitoring/dashboard
npm run build
```

This creates a `dist/` folder with static files.

### 3.3 Deploy to Firebase Hosting

```bash
# Install Firebase CLI
npm install -g firebase-tools

# Login to Firebase
firebase login

# Initialize Firebase in dashboard folder
cd ~/patient-monitoring/dashboard
firebase init hosting

# When prompted:
# - Select your GCP project
# - Public directory: dist
# - Single-page app: Yes
# - Don't overwrite index.html

# Deploy
firebase deploy --only hosting
```

### 3.4 Get Your Live URL

After deployment, Firebase will show:
```
✓ Hosting URL: https://your-project-id.web.app
```

---

## Part 4: Verify Everything Works

### Checklist

- [ ] VM is running
- [ ] API responds: `curl http://EXTERNAL_IP:5050/`
- [ ] Data endpoint works: `curl http://EXTERNAL_IP:5050/api/data`
- [ ] Firebase URL loads the dashboard
- [ ] Dashboard shows real patient data (not demo mode)
- [ ] Alerts appear in the feed
- [ ] Patient detail modal works

---

## Troubleshooting

### API not accessible externally
```bash
# Check firewall rule exists
gcloud compute firewall-rules list | grep 5050

# Check service is running
sudo systemctl status patient-monitor-api

# Check it's listening on 0.0.0.0
sudo netstat -tlnp | grep 5050
```

### CORS errors in browser
Update `dashboard_api.py` to allow your Firebase domain:
```python
CORS(app, origins=[
    'http://localhost:5173',
    'http://localhost:3000',
    'https://your-project-id.web.app',
    'https://your-project-id.firebaseapp.com'
])
```

### Services not starting
```bash
# Check logs for errors
sudo journalctl -u patient-monitor-api -n 50

# Common issues:
# - Wrong Python path in service file
# - Missing dependencies
# - Config file issues
```

### Producers finish and stop
The producers will stop when they've sent all the data. For a continuous demo:
- Modify producers to loop infinitely
- Or use a larger dataset
- Or restart them periodically

---

## Optional: Loop Producers Continuously

Modify `producer.py` to loop forever:

```python
# At the end of main(), wrap in while True:
def main():
    while True:
        # ... existing producer code ...
        print("Restarting producer from beginning...")
        time.sleep(5)
```

Same for `lab_producer.py`.

---

## Cost Estimate

| Resource | Cost |
|----------|------|
| GCE e2-medium | ~$25/month |
| Firebase Hosting | Free tier |
| Confluent Cloud | Free tier (demo usage) |

For the hackathon demo period (~1 week), cost should be < $10.

---

## Quick Commands Reference

```bash
# SSH into VM
gcloud compute ssh patient-monitor-vm --zone=us-central1-a

# Restart all services
sudo systemctl restart patient-monitor-api patient-monitor-vitals patient-monitor-labs

# View all logs
sudo journalctl -u patient-monitor-api -u patient-monitor-vitals -u patient-monitor-labs -f

# Stop everything
sudo systemctl stop patient-monitor-api patient-monitor-vitals patient-monitor-labs

# Get external IP
gcloud compute instances describe patient-monitor-vm --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```
