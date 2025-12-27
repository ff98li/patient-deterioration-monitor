"""
Dashboard API Backend

Flask server that provides REST API endpoints for the React dashboard.
Serves patient data, alerts, and statistics from shared_state.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import shared_state

app = Flask(__name__)

# Enable CORS for React frontend (development on different port)
#CORS(app, origins=['http://localhost:5173', 'http://localhost:3000', 'http://127.0.0.1:5173'])
CORS(app, origins=[
    'http://localhost:5173', 
    'http://localhost:3000', 
    'http://127.0.0.1:5173',
    'https://*.run.app',
    'https://patient-deterioration-monitor.ffli.dev'
])


@app.route('/')
def index():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'Patient Deterioration Monitor API',
        'version': '1.0.0'
    })


@app.route('/api/data')
def get_data():
    """
    Main data endpoint for dashboard.
    Returns patients, alerts, and stats in format expected by React frontend.
    """
    data = shared_state.get_dashboard_data()
    return jsonify(data)


@app.route('/api/patients')
def get_patients():
    """Get all patients sorted by risk level."""
    data = shared_state.get_dashboard_data()
    return jsonify(data['patients'])


@app.route('/api/patients/<int:stay_id>')
def get_patient_endpoint(stay_id: int):
    """Get a specific patient by stay_id."""
    patient = shared_state.get_patient(stay_id)
    
    if patient:
        return jsonify(patient)
    else:
        return jsonify({'error': 'Patient not found'}), 404

# @app.route('/api/patients/<int:stay_id>')
# def get_patient(stay_id: int):
#     """Get a specific patient by stay_id."""
#     data = shared_state.get_dashboard_data()
#     patient = next((p for p in data['patients'] if p['stay_id'] == stay_id), None)
    
#     if patient:
#         return jsonify(patient)
#     else:
#         return jsonify({'error': 'Patient not found'}), 404


@app.route('/api/patients/<int:stay_id>/history')
def get_patient_history(stay_id: int):
    """Get historical readings for a patient (for trend charts)."""
    history = shared_state.get_patient_history(stay_id)
    return jsonify(history)


@app.route('/api/alerts')
def get_alerts():
    """Get all alerts."""
    data = shared_state.get_dashboard_data()
    return jsonify(data['alerts'])


@app.route('/api/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    success = shared_state.acknowledge_alert(alert_id)
    if success:
        return jsonify({'status': 'acknowledged', 'id': alert_id})
    else:
        return jsonify({'error': 'Alert not found'}), 404


@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics."""
    data = shared_state.get_dashboard_data()
    return jsonify(data['stats'])


if __name__ == '__main__':
    print("=" * 60)
    print("Patient Deterioration Monitor - Dashboard API")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /api/data                    - All dashboard data")
    print("  GET  /api/patients                - All patients")
    print("  GET  /api/patients/<id>           - Single patient")
    print("  GET  /api/patients/<id>/history   - Patient trend history")
    print("  GET  /api/alerts                  - All alerts")
    print("  POST /api/alerts/<id>/acknowledge - Acknowledge alert")
    print("  GET  /api/stats                   - Statistics")
    print("\n" + "=" * 60)
    
    app.run(host='0.0.0.0', port=5050, debug=True, threaded=True)
