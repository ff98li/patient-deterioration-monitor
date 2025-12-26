"""
Lab Analysis Module: Clinical interpretation of laboratory values

This module provides functions to analyze lab results and flag abnormalities
that may indicate patient deterioration, particularly for sepsis detection.
"""

from typing import Dict, Tuple, List


# Clinical reference ranges and critical thresholds
# Format: (low_critical, low_normal, high_normal, high_critical)
LAB_REFERENCE_RANGES = {
    'lactate': {
        'ranges': (None, 0.5, 2.0, 4.0),  # >4 is severe, >2 is elevated
        'unit': 'mmol/L',
        'clinical_significance': 'Tissue hypoxia, sepsis marker'
    },
    'creatinine': {
        'ranges': (None, 0.6, 1.2, 4.0),  # >4 suggests severe renal impairment
        'unit': 'mg/dL',
        'clinical_significance': 'Kidney function'
    },
    'potassium': {
        'ranges': (2.5, 3.5, 5.0, 6.5),  # Both hypo and hyperkalemia are dangerous
        'unit': 'mEq/L',
        'clinical_significance': 'Cardiac arrhythmia risk'
    },
    'wbc': {
        'ranges': (2.0, 4.0, 11.0, 30.0),  # <4 or >11 suggests infection/sepsis
        'unit': 'K/uL',
        'clinical_significance': 'Infection/sepsis indicator'
    },
    'hemoglobin': {
        'ranges': (6.0, 12.0, 17.0, None),  # <7 often triggers transfusion
        'unit': 'g/dL',
        'clinical_significance': 'Anemia, bleeding'
    },
    'platelet': {
        'ranges': (20.0, 150.0, 400.0, None),  # <50 is severe thrombocytopenia
        'unit': 'K/uL',
        'clinical_significance': 'Coagulation, sepsis marker'
    },
    'bicarbonate': {
        'ranges': (10.0, 22.0, 28.0, None),  # <18 may indicate metabolic acidosis
        'unit': 'mEq/L',
        'clinical_significance': 'Acid-base balance'
    },
    'glucose': {
        'ranges': (40.0, 70.0, 140.0, 400.0),  # Hypoglycemia is dangerous
        'unit': 'mg/dL',
        'clinical_significance': 'Metabolic status'
    },
    'sodium': {
        'ranges': (120.0, 135.0, 145.0, 160.0),
        'unit': 'mEq/L',
        'clinical_significance': 'Fluid/electrolyte balance'
    },
    'chloride': {
        'ranges': (80.0, 96.0, 106.0, 120.0),
        'unit': 'mEq/L',
        'clinical_significance': 'Electrolyte balance'
    }
}


def analyze_lab_value(lab_type: str, value: float) -> Dict:
    """
    Analyze a single lab value against clinical reference ranges.
    
    Returns:
        Dict with 'status', 'severity', 'message'
    """
    if lab_type not in LAB_REFERENCE_RANGES:
        return {
            'status': 'UNKNOWN',
            'severity': 0,
            'message': f'Unknown lab type: {lab_type}'
        }
    
    ref = LAB_REFERENCE_RANGES[lab_type]
    low_crit, low_norm, high_norm, high_crit = ref['ranges']
    unit = ref['unit']
    
    # Check critical low
    if low_crit is not None and value < low_crit:
        return {
            'status': 'CRITICAL_LOW',
            'severity': 3,
            'message': f'{lab_type}: {value} {unit} (CRITICAL LOW, normal: {low_norm}-{high_norm})'
        }
    
    # Check critical high
    if high_crit is not None and value > high_crit:
        return {
            'status': 'CRITICAL_HIGH',
            'severity': 3,
            'message': f'{lab_type}: {value} {unit} (CRITICAL HIGH, normal: {low_norm}-{high_norm})'
        }
    
    # Check abnormal low
    if low_norm is not None and value < low_norm:
        return {
            'status': 'LOW',
            'severity': 1,
            'message': f'{lab_type}: {value} {unit} (LOW, normal: {low_norm}-{high_norm})'
        }
    
    # Check abnormal high
    if high_norm is not None and value > high_norm:
        return {
            'status': 'HIGH',
            'severity': 2 if high_crit and value > (high_norm + high_crit) / 2 else 1,
            'message': f'{lab_type}: {value} {unit} (HIGH, normal: {low_norm}-{high_norm})'
        }
    
    # Normal
    return {
        'status': 'NORMAL',
        'severity': 0,
        'message': f'{lab_type}: {value} {unit} (normal)'
    }


def analyze_labs(labs: Dict[str, float]) -> Dict:
    """
    Analyze a set of lab results.
    
    Returns:
        Dict with 'lab_scores', 'total_severity', 'risk_level', 'abnormal_labs', 'alerts'
    """
    lab_scores = {}
    abnormal_labs = []
    alerts = []
    total_severity = 0
    
    for lab_type, value in labs.items():
        if value is None:
            continue
            
        analysis = analyze_lab_value(lab_type, value)
        lab_scores[lab_type] = analysis
        total_severity += analysis['severity']
        
        if analysis['status'] not in ['NORMAL', 'UNKNOWN']:
            abnormal_labs.append(analysis['message'])
            
        if analysis['severity'] >= 2:
            alerts.append({
                'lab': lab_type,
                'value': value,
                'status': analysis['status'],
                'severity': analysis['severity']
            })
    
    # Determine overall risk level
    if total_severity >= 6:
        risk_level = 'CRITICAL'
    elif total_severity >= 4:
        risk_level = 'HIGH'
    elif total_severity >= 2:
        risk_level = 'MEDIUM'
    elif total_severity >= 1:
        risk_level = 'LOW'
    else:
        risk_level = 'NORMAL'
    
    return {
        'lab_scores': lab_scores,
        'total_severity': total_severity,
        'risk_level': risk_level,
        'abnormal_labs': abnormal_labs,
        'alerts': alerts
    }


def check_sepsis_indicators(labs: Dict[str, float], vitals: Dict[str, float] = None) -> Dict:
    """
    Check for sepsis indicators based on labs and optionally vitals.
    
    Sepsis criteria often include:
    - Elevated lactate (>2 mmol/L)
    - WBC abnormality (<4 or >12 K/uL)
    - Elevated creatinine (acute kidney injury)
    - Thrombocytopenia (low platelets)
    
    Combined with vitals (if provided):
    - Tachycardia (HR > 90)
    - Tachypnea (RR > 20)
    - Hypotension (SBP < 100)
    - Fever or hypothermia
    """
    indicators = []
    score = 0
    
    # Lab indicators
    if 'lactate' in labs:
        if labs['lactate'] > 4:
            indicators.append(f"Severe hyperlactatemia ({labs['lactate']} mmol/L)")
            score += 3
        elif labs['lactate'] > 2:
            indicators.append(f"Elevated lactate ({labs['lactate']} mmol/L)")
            score += 2
    
    if 'wbc' in labs:
        if labs['wbc'] > 12 or labs['wbc'] < 4:
            indicators.append(f"Abnormal WBC ({labs['wbc']} K/uL)")
            score += 1
    
    if 'creatinine' in labs:
        if labs['creatinine'] > 2.0:
            indicators.append(f"Elevated creatinine ({labs['creatinine']} mg/dL)")
            score += 1
    
    if 'platelet' in labs:
        if labs['platelet'] < 100:
            indicators.append(f"Thrombocytopenia ({labs['platelet']} K/uL)")
            score += 1
    
    # Vital indicators (if provided)
    if vitals:
        if vitals.get('heart_rate', 0) > 90:
            indicators.append(f"Tachycardia (HR {vitals['heart_rate']})")
            score += 1
        if vitals.get('respiratory_rate', 0) > 20:
            indicators.append(f"Tachypnea (RR {vitals['respiratory_rate']})")
            score += 1
        if vitals.get('systolic_bp', 999) < 100:
            indicators.append(f"Hypotension (SBP {vitals['systolic_bp']})")
            score += 2
        temp = vitals.get('temperature_f', 98.6)
        if temp > 100.4 or temp < 96.8:
            indicators.append(f"Temperature abnormality ({temp}°F)")
            score += 1
    
    # Determine sepsis risk
    if score >= 5:
        risk = 'HIGH'
        recommendation = 'Consider sepsis workup and early intervention'
    elif score >= 3:
        risk = 'MODERATE'
        recommendation = 'Monitor closely for sepsis progression'
    elif score >= 1:
        risk = 'LOW'
        recommendation = 'Some concerning findings, continue monitoring'
    else:
        risk = 'MINIMAL'
        recommendation = 'No significant sepsis indicators'
    
    return {
        'sepsis_score': score,
        'sepsis_risk': risk,
        'indicators': indicators,
        'recommendation': recommendation
    }


def format_labs_for_display(labs: Dict[str, float], units: Dict[str, str] = None) -> str:
    """Format lab results for console display."""
    parts = []
    for lab_type, value in labs.items():
        unit = units.get(lab_type, '') if units else ''
        # Abbreviate lab names for display
        abbrev = {
            'lactate': 'LAC',
            'creatinine': 'Cr',
            'potassium': 'K',
            'wbc': 'WBC',
            'hemoglobin': 'Hgb',
            'platelet': 'Plt',
            'bicarbonate': 'HCO3',
            'glucose': 'Glu',
            'sodium': 'Na',
            'chloride': 'Cl'
        }.get(lab_type, lab_type[:3].upper())
        parts.append(f"{abbrev}:{value:.1f}")
    return " | ".join(parts)


def format_labs_for_ai(labs: Dict[str, float], units: Dict[str, str] = None) -> str:
    """Format lab results for AI interpretation prompt."""
    lines = []
    for lab_type, value in labs.items():
        ref = LAB_REFERENCE_RANGES.get(lab_type, {})
        unit = units.get(lab_type, ref.get('unit', '')) if units else ref.get('unit', '')
        ranges = ref.get('ranges', (None, None, None, None))
        low_norm, high_norm = ranges[1], ranges[2]
        
        range_str = f"(normal: {low_norm}-{high_norm} {unit})" if low_norm and high_norm else ""
        lines.append(f"  - {lab_type}: {value} {unit} {range_str}")
    
    return "\n".join(lines)
