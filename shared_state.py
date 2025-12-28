"""
Shared State Module for Dashboard Integration

This module maintains the real-time state of patients, alerts, and statistics
for consumption by the React dashboard frontend.
"""

import threading
from datetime import datetime, UTC
from collections import defaultdict
from typing import Dict, List, Optional, Any
import uuid


# Thread-safe lock
_lock = threading.Lock()

# Patient data storage - now stores complete patient objects
_patients: Dict[int, Dict[str, Any]] = {}

# Alert storage
_alerts: List[Dict[str, Any]] = []

# Statistics
_stats = {
    'total_patients': 0,
    'critical_count': 0,
    'high_count': 0,
    'medium_count': 0,
    'low_count': 0,
    'normal_count': 0,
    'alerts_today': 0,
    'stream_status': 'active',
    'last_vitals_received': None,
    'last_labs_received': None,
}

# Patient history for trends (stores last N readings)
_patient_history: Dict[int, List[Dict]] = defaultdict(list)
HISTORY_SIZE = 100  # Keep last 100 readings per patient


def update_patient(stay_id: int, data: Dict[str, Any]) -> None:
    """
    Update patient data with complete information for dashboard display.
    
    Expected data structure:
    {
        'subject_id': int,
        'stay_id': int,
        'timestamp': str,
        'vitals': {...},
        'mews_score': int,
        'risk_level': str,
        'components': {...},
        # Optional - added by multi-stream consumer:
        'labs': {...},
        'labs_age_minutes': float,
        'sepsis_risk': str,
        'ai_assessment': str,
        'ai_confidence': str,
        'ai_recommendation': str,
        'confidence_reasoning': str,
        'trend_confirmed': bool,
        'consecutive_readings': int,
    }
    """
    with _lock:
        # Get existing patient data or create new
        existing = _patients.get(stay_id, {})
        
        # Build complete patient object
        patient = {
            'stay_id': stay_id,
            'subject_id': data.get('subject_id', existing.get('subject_id', 0)),
            'mews_score': data.get('mews_score', existing.get('mews_score', 0)),
            'risk_level': data.get('risk_level', existing.get('risk_level', 'NORMAL')),
            'last_updated': datetime.now(UTC).isoformat(),
            
            # Vitals - using temperature_c (Celsius)
            'vitals': {
                'heart_rate': data.get('vitals', {}).get('heart_rate') or existing.get('vitals', {}).get('heart_rate', 0),
                'respiratory_rate': data.get('vitals', {}).get('respiratory_rate') or existing.get('vitals', {}).get('respiratory_rate', 0),
                'spo2': data.get('vitals', {}).get('spo2') or existing.get('vitals', {}).get('spo2', 0),
                'systolic_bp': data.get('vitals', {}).get('systolic_bp') or existing.get('vitals', {}).get('systolic_bp', 0),
                'diastolic_bp': data.get('vitals', {}).get('diastolic_bp') or existing.get('vitals', {}).get('diastolic_bp', 0),
                # 'temperature_c': data.get('vitals', {}).get('temperature_c') or existing.get('vitals', {}).get('temperature_c', 0),
                # 1. Use temperature_c if available
                # 2. Convert temperature_f to Celsius if only F is available
                # 3. Fall back to existing value
                'temperature_c': (
                    data.get('vitals', {}).get('temperature_c') or
                    (round(((data.get('vitals', {}).get('temperature_f') or 0) - 32) * 5/9, 1)
                     if data.get('vitals', {}).get('temperature_f') else None) or
                    existing.get('vitals', {}).get('temperature_c', 0)
                ),
            },
            
            # Labs (may come from separate update) - preserve existing
            'labs': data.get('labs') or existing.get('labs', {
                'lactate': 0,
                'creatinine': 0,
                'wbc': 0,
                'potassium': 0,
            }),
            # Preserve labs_received_at if exists
            'labs_received_at': existing.get('labs_received_at'),
            
            # Risk indicators
            'sepsis_risk': data.get('sepsis_risk', existing.get('sepsis_risk', 'LOW')),
            
            # AI interpretation
            'ai_confidence': data.get('ai_confidence', existing.get('ai_confidence', 'MEDIUM')),
            'ai_assessment': data.get('ai_assessment', existing.get('ai_assessment', 'Awaiting assessment...')),
            'ai_recommendation': data.get('ai_recommendation', existing.get('ai_recommendation', 'Continue monitoring.')),
            'confidence_reasoning': data.get('confidence_reasoning', existing.get('confidence_reasoning', '')),
            
            # Alert confirmation
            'trend_confirmed': data.get('trend_confirmed', existing.get('trend_confirmed', False)),
            'consecutive_readings': data.get('consecutive_readings', existing.get('consecutive_readings', 0)),
        }
        
        _patients[stay_id] = patient
        
        # Update history for trends
        history_entry = {
            'timestamp': data.get('timestamp', datetime.now(UTC).isoformat()),
            'mews_score': patient['mews_score'],
            'heart_rate': patient['vitals']['heart_rate'],
            'spo2': patient['vitals']['spo2'],
            'respiratory_rate': patient['vitals']['respiratory_rate'],
        }
        _patient_history[stay_id].append(history_entry)
        if len(_patient_history[stay_id]) > HISTORY_SIZE:
            _patient_history[stay_id] = _patient_history[stay_id][-HISTORY_SIZE:]
        
        # Update stats
        _stats['last_vitals_received'] = datetime.now(UTC).isoformat()
        _update_counts()


def update_patient_labs(stay_id: int, labs_data: Dict[str, Any]) -> None:
    """Update just the labs portion of a patient's data."""
    with _lock:
        # Create patient if doesn't exist
        if stay_id not in _patients:
            _patients[stay_id] = {
                'stay_id': stay_id,
                'subject_id': 0,
                'mews_score': 0,
                'risk_level': 'NORMAL',
                'last_updated': datetime.now(UTC).isoformat(),
                'vitals': {'heart_rate': 0, 'respiratory_rate': 0, 'spo2': 0, 'systolic_bp': 0, 'diastolic_bp': 0, 'temperature_c': 0},
                'labs': {'lactate': 0, 'creatinine': 0, 'wbc': 0, 'potassium': 0},
                'labs_received_at': None,
                'sepsis_risk': 'LOW',
                'ai_confidence': 'MEDIUM',
                'ai_assessment': 'Awaiting assessment...',
                'ai_recommendation': 'Continue monitoring.',
                'confidence_reasoning': '',
                'trend_confirmed': False,
                'consecutive_readings': 0,
            }
        
        _patients[stay_id]['labs'] = {
            'lactate': labs_data.get('labs', {}).get('lactate', 0),
            'creatinine': labs_data.get('labs', {}).get('creatinine', 0),
            'wbc': labs_data.get('labs', {}).get('wbc', 0),
            'potassium': labs_data.get('labs', {}).get('potassium', 0),
        }
        # Store timestamp when labs were received
        _patients[stay_id]['labs_received_at'] = datetime.now(UTC)
        
        _stats['last_labs_received'] = datetime.now(UTC).isoformat()


def update_patient_ai(stay_id: int, ai_data: Dict[str, Any]) -> None:
    """Update AI interpretation for a patient."""
    with _lock:
        if stay_id in _patients:
            _patients[stay_id].update({
                'ai_confidence': ai_data.get('confidence', 'MEDIUM'),
                'ai_assessment': ai_data.get('interpretation', ''),
                'ai_recommendation': ', '.join(ai_data.get('recommended_actions', [])),
                'confidence_reasoning': ai_data.get('confidence_reasoning', ''),
            })


def update_patient_alert_status(stay_id: int, confirmed: bool, count: int) -> None:
    """Update alert confirmation status for a patient."""
    with _lock:
        if stay_id in _patients:
            _patients[stay_id]['trend_confirmed'] = confirmed
            _patients[stay_id]['consecutive_readings'] = count


def _update_counts() -> None:
    """Update risk level counts (must be called within lock)."""
    counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'NORMAL': 0}
    for patient in _patients.values():
        risk = patient.get('risk_level', 'NORMAL')
        if risk in counts:
            counts[risk] += 1
    
    _stats['total_patients'] = len(_patients)
    _stats['critical_count'] = counts['CRITICAL']
    _stats['high_count'] = counts['HIGH']
    _stats['medium_count'] = counts['MEDIUM']
    _stats['low_count'] = counts['LOW']
    _stats['normal_count'] = counts['NORMAL']


def _calculate_labs_age(patient: Dict[str, Any]) -> int:
    """Calculate labs age in minutes from labs_received_at timestamp."""
    labs_received_at = patient.get('labs_received_at')
    if labs_received_at is None:
        return 999
    age_seconds = (datetime.now(UTC) - labs_received_at).total_seconds()
    return int(age_seconds / 60)


def add_alert(alert: Dict[str, Any]) -> None:
    """Add a new alert."""
    with _lock:
        alert_obj = {
            'id': str(uuid.uuid4())[:8],
            'type': alert.get('type', 'ALERT'),
            'stay_id': alert.get('stay_id', 0),
            'message': alert.get('message', ''),
            'timestamp': datetime.now(UTC).isoformat(),
            'is_acknowledged': False,
            'severity': 'critical' if alert.get('severity') == 'CRITICAL' else 'warning',
        }
        _alerts.insert(0, alert_obj)
        
        # Keep only last 100 alerts
        if len(_alerts) > 100:
            _alerts[:] = _alerts[:100]
        
        _stats['alerts_today'] = _stats.get('alerts_today', 0) + 1


def acknowledge_alert(alert_id: str) -> bool:
    """Acknowledge an alert by ID."""
    with _lock:
        for alert in _alerts:
            if alert['id'] == alert_id:
                alert['is_acknowledged'] = True
                return True
        return False


def get_dashboard_data() -> Dict[str, Any]:
    """
    Get all data needed for the dashboard in the format expected by React frontend.
    """
    with _lock:
        # Build patient list with calculated labs age
        patients_with_age = []
        for p in _patients.values():
            patient = p.copy()
            # Calculate labs age dynamically
            patient['labs_age_minutes'] = _calculate_labs_age(p)
            # Remove internal field before sending to frontend
            patient.pop('labs_received_at', None)
            patients_with_age.append(patient)
        
        # Sort patients by risk level
        risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'NORMAL': 4}
        sorted_patients = sorted(
            patients_with_age,
            key=lambda p: risk_order.get(p.get('risk_level', 'NORMAL'), 5)
        )
        
        return {
            'patients': sorted_patients,
            'alerts': _alerts,
            'stats': {
                'total_patients': _stats['total_patients'],
                'critical_count': _stats['critical_count'],
                'high_count': _stats['high_count'],
                'alerts_today': _stats['alerts_today'],
                'stream_status': _stats['stream_status'],
                'last_vitals_received': _stats['last_vitals_received'],
            }
        }


def get_patient(stay_id: int) -> Optional[Dict[str, Any]]:
    """Get a single patient by stay_id with calculated labs age."""
    with _lock:
        if stay_id not in _patients:
            return None
        patient = _patients[stay_id].copy()
        # Calculate labs age dynamically
        patient['labs_age_minutes'] = _calculate_labs_age(_patients[stay_id])
        # Remove internal field
        patient.pop('labs_received_at', None)
        return patient


def get_patient_history(stay_id: int) -> List[Dict]:
    """Get historical readings for a patient (for trend charts)."""
    with _lock:
        return list(_patient_history.get(stay_id, []))


def reset() -> None:
    """Reset all state (for testing)."""
    with _lock:
        _patients.clear()
        _alerts.clear()
        _patient_history.clear()
        _stats.update({
            'total_patients': 0,
            'critical_count': 0,
            'high_count': 0,
            'medium_count': 0,
            'low_count': 0,
            'normal_count': 0,
            'alerts_today': 0,
            'stream_status': 'active',
            'last_vitals_received': None,
            'last_labs_received': None,
        })
