"""
Model: Patient Deterioration Scoring

Uses Modified Early Warning Score (MEWS) as a clinically-validated baseline,
enhanced with Vertex AI for natural language interpretation.

MEWS is a simple scoring system used in hospitals to identify patients
at risk of deterioration. Higher scores indicate higher risk.

References:
- Original MEWS: Subbe CP, Kruger M, Rutherford P, Gemmel L. Validation of a 
  modified Early Warning Score in medical admissions. QJM. 2001;94(10):521-526.
  doi:10.1093/qjmed/94.10.521

- SpO2 addition (ViEWS): Prytherch DR, Smith GB, Schmidt PE, Featherstone PI. 
  ViEWS--Towards a national early warning score for detecting adult inpatient 
  deterioration. Resuscitation. 2010;81(8):932-937.
  doi:10.1016/j.resuscitation.2010.04.014

- NEWS2 (current UK standard): Royal College of Physicians. National Early 
  Warning Score (NEWS) 2. 2017.
"""

import time
from typing import Dict
from google import genai
from google.genai import types, Client

# Vertex AI Gemini Model ID
MODEL_ID = "gemini-2.5-flash"
MIN_AI_INTERVAL = 2  # Minimum seconds between AI calls
_last_ai_call = 0
_max_retries = 3

# MEWS Scoring Tables (clinically validated thresholds)
# Based on Subbe et al. 2001, with SpO2 from Prytherch et al. 2010 (ViEWS)
MEWS_CRITERIA = {
    'systolic_bp': [
        (0, 70, 3),      # <= 70: score 3
        (71, 80, 2),     # 71-80: score 2
        (81, 100, 1),    # 81-100: score 1
        (101, 199, 0),   # 101-199: score 0 (normal)
        (200, 999, 2),   # >= 200: score 2
    ],
    'heart_rate': [
        (0, 40, 2),      # <= 40: score 2
        (41, 50, 1),     # 41-50: score 1
        (51, 100, 0),    # 51-100: score 0 (normal)
        (101, 110, 1),   # 101-110: score 1
        (111, 129, 2),   # 111-129: score 2
        (130, 999, 3),   # >= 130: score 3
    ],
    'respiratory_rate': [
        (0, 8, 2),       # <= 8: score 2
        (9, 14, 0),      # 9-14: score 0 (normal)
        (15, 20, 1),     # 15-20: score 1
        (21, 29, 2),     # 21-29: score 2
        (30, 999, 3),    # >= 30: score 3
    ],
    # Temperature in Celsius (Subbe et al. 2001)
    # Note: Original MEWS only has scores 0 and 2 for temperature
    'temperature_c': [
        (0, 34.9, 2),      # < 35°C: score 2 (hypothermia)
        (35.0, 38.4, 0),   # 35.0-38.4°C: score 0 (normal)
        (38.5, 999, 2),    # >= 38.5°C: score 2 (fever)
    ],
    # SpO2 scoring based on ViEWS (Prytherch et al. 2010)
    # Added to enhance MEWS for ICU monitoring
    'spo2': [
        (0, 91, 3),      # <= 91%: score 3 (critical)
        (92, 93, 2),     # 92-93%: score 2
        (94, 95, 1),     # 94-95%: score 1
        (96, 100, 0),    # >= 96%: score 0 (normal)
    ],
}


def calculate_mews_component(vital_type: str, value: float) -> int:
    """Calculate MEWS score component for a single vital sign."""
    if vital_type not in MEWS_CRITERIA:
        return 0
    
    for low, high, score in MEWS_CRITERIA[vital_type]:
        if low <= value <= high:
            return score
    
    return 0


def calculate_mews_score(vitals: Dict[str, float]) -> Dict:
    """
    Calculate total MEWS score from vital signs.
    
    Handles both temperature_c and temperature_f (converts F to C).
    
    Returns:
        Dict with total score, component breakdown, and risk level
    """
    components = {}
    total_score = 0
    
    # Create a working copy to handle temperature conversion
    vitals_processed = vitals.copy()
    
    # Handle temperature: prefer Celsius, convert Fahrenheit if needed
    if 'temperature_f' in vitals_processed and 'temperature_c' not in vitals_processed:
        # Convert Fahrenheit to Celsius
        temp_f = vitals_processed.get('temperature_f')
        if temp_f is not None:
            vitals_processed['temperature_c'] = (temp_f - 32) * 5 / 9
    
    for vital_type, value in vitals_processed.items():
        if value is not None and vital_type in MEWS_CRITERIA:
            score = calculate_mews_component(vital_type, value)
            components[vital_type] = {
                'value': value,
                'score': score
            }
            total_score += score
    
    # Determine risk level
    if total_score >= 7:
        risk_level = 'CRITICAL'
        risk_score = 1.0
    elif total_score >= 5:
        risk_level = 'HIGH'
        risk_score = 0.8
    elif total_score >= 3:
        risk_level = 'MEDIUM'
        risk_score = 0.5
    elif total_score >= 1:
        risk_level = 'LOW'
        risk_score = 0.2
    else:
        risk_level = 'NORMAL'
        risk_score = 0.0
    
    return {
        'mews_total': total_score,
        'components': components,
        'risk_level': risk_level,
        'risk_score': risk_score,  # Normalized 0-1 for thresholding
    }


def get_ai_interpretation(
    vitals: Dict[str, float],
    mews_result: Dict,
    project_id: str,
    region: str = "us-central1"
) -> Dict[str, str]:
    """
    Use Vertex AI Gemini to generate a clinical interpretation with confidence.
    
    Returns:
        Dict with 'interpretation', 'confidence', and 'confidence_reasoning'
    """
    global _last_ai_call
    
    # Rate limiting
    elapsed = time.time() - _last_ai_call
    if elapsed < MIN_AI_INTERVAL:
        time.sleep(MIN_AI_INTERVAL - elapsed)
    
    # Count available vitals for confidence assessment
    available_vitals = [k for k, v in vitals.items() if v is not None]
    missing_vitals = [k for k in ['heart_rate', 'systolic_bp', 'respiratory_rate', 'spo2', 'temperature_c'] 
                     if k not in available_vitals]
    
    prompt = f"""You are a clinical decision support assistant analyzing patient vital signs.

Vital Signs:
{format_vitals_for_prompt(vitals)}

MEWS Score: {mews_result['mews_total']} ({mews_result['risk_level']} risk)

Component Scores:
{format_components_for_prompt(mews_result['components'])}

Available vitals: {len(available_vitals)}/7
Missing vitals: {', '.join(missing_vitals) if missing_vitals else 'None'}

Respond in this EXACT JSON format (no markdown, no code blocks):
{{
    "interpretation": "2-3 sentence clinical interpretation of the patient's condition and any immediate concerns",
    "confidence": "LOW|MEDIUM|HIGH",
    "confidence_reasoning": "Brief explanation of confidence level based on data completeness and clinical clarity"
}}

Confidence guidelines:
- HIGH: Complete vital signs, clear clinical picture, unambiguous risk level
- MEDIUM: Most vitals available, some clinical uncertainty
- LOW: Missing key vitals, conflicting signals, or unusual presentation"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = Client(
                vertexai=True,
                project=project_id,
                location=region
            )
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
            )
            _last_ai_call = time.time()
            
            # Parse JSON response
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            import json
            result = json.loads(response_text)
            return result
        
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return {
                "interpretation": response.text if 'response' in dir() else "Unable to parse AI response",
                "confidence": "LOW",
                "confidence_reasoning": "Response parsing error"
            }
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                time.sleep(wait_time)
                continue
            return {
                "interpretation": f"AI interpretation unavailable: {str(e)}",
                "confidence": "UNKNOWN",
                "confidence_reasoning": "API error"
            }
    
    return {
        "interpretation": "AI interpretation unavailable: max retries exceeded",
        "confidence": "UNKNOWN", 
        "confidence_reasoning": "Max retries exceeded"
    }


def format_vitals_for_prompt(vitals: Dict[str, float]) -> str:
    """Format vitals dictionary for the AI prompt."""
    lines = []
    vital_labels = {
        'heart_rate': 'Heart Rate',
        'systolic_bp': 'Systolic BP',
        'diastolic_bp': 'Diastolic BP',
        'respiratory_rate': 'Respiratory Rate',
        'spo2': 'SpO2',
        'temperature_c': 'Temperature',
        'temperature_f': 'Temperature',
        'mean_arterial_pressure': 'MAP'
    }
    for key, value in vitals.items():
        if value is not None:
            label = vital_labels.get(key, key)
            unit = get_unit(key)
            lines.append(f"- {label}: {value}{unit}")
    return '\n'.join(lines)


def format_components_for_prompt(components: Dict) -> str:
    """Format MEWS components for the AI prompt."""
    lines = []
    for vital_type, data in components.items():
        lines.append(f"- {vital_type}: {data['value']} (score: {data['score']})")
    return '\n'.join(lines)


def get_unit(vital_type: str) -> str:
    """Get the unit for a vital sign type."""
    units = {
        'heart_rate': ' bpm',
        'systolic_bp': ' mmHg',
        'diastolic_bp': ' mmHg',
        'mean_arterial_pressure': ' mmHg',
        'respiratory_rate': ' /min',
        'spo2': '%',
        'temperature_c': '°C',
        'temperature_f': '°F'
    }
    return units.get(vital_type, '')


# Example usage
if __name__ == "__main__":
    # Test with sample vitals (now using Celsius)
    sample_vitals = {
        'heart_rate': 125,
        'systolic_bp': 85,
        'respiratory_rate': 24,
        'spo2': 93,
        'temperature_c': 38.6  # Celsius
    }
    
    result = calculate_mews_score(sample_vitals)
    print("MEWS Assessment")
    print("=" * 40)
    print(f"Total Score: {result['mews_total']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Risk Score: {result['risk_score']}")
    print("\nComponent Breakdown:")
    for vital, data in result['components'].items():
        print(f"  {vital}: {data['value']} -> score {data['score']}")
