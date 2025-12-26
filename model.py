"""
Model: Patient Deterioration Scoring

Uses Modified Early Warning Score (MEWS) as a clinically-validated baseline,
enhanced with Vertex AI for natural language interpretation.

MEWS is a simple scoring system used in hospitals to identify patients
at risk of deterioration. Higher scores indicate higher risk.
"""

import time
from typing import Dict
#import vertexai
#from vertexai.generative_models import GenerativeModel
from google import genai
from google.genai import types, Client

# Vertex AI Gemini Model ID
MODEL_ID = "gemini-2.5-flash"
MIN_AI_INTERVAL = 2  # Minimum seconds between AI calls
_last_ai_call = 0
_max_retries = 3

# MEWS Scoring Tables (clinically validated thresholds)
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
    'temperature_f': [
        (0, 95, 2),      # <= 95°F (35°C): score 2
        (95.1, 101.1, 0),  # Normal range: score 0
        (101.2, 102.2, 1), # Low fever: score 1
        (102.3, 999, 2),   # High fever: score 2
    ],
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
    
    Returns:
        Dict with total score, component breakdown, and risk level
    """
    components = {}
    total_score = 0
    
    for vital_type, value in vitals.items():
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
    missing_vitals = [k for k in ['heart_rate', 'systolic_bp', 'respiratory_rate', 'spo2', 'temperature_f'] 
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


##def get_ai_interpretation(
##    vitals: Dict[str, float],
##    mews_result: Dict,
##    project_id: str,
##    region: str = "asia-southeast1"
##) -> str:
##    """
##    Use Vertex AI Gemini to generate a clinical interpretation.
##    
##    This adds value beyond the simple score by providing context
##    and suggested actions.
##    """
##
##    global _last_ai_call
##    global _max_retries
##    elapsed = time.time() - _last_ai_call
##    if elapsed < MIN_AI_INTERVAL:
##        time.sleep(MIN_AI_INTERVAL - elapsed)
##
##    prompt = f"""You are a clinical decision support assistant. 
##            Based on the following patient vital signs and MEWS score, provide a brief 
##            (2-3 sentence) clinical interpretation and any immediate concerns.
##
##            Vital Signs:
##            {format_vitals_for_prompt(vitals)}
##            
##            MEWS Score: {mews_result['mews_total']} ({mews_result['risk_level']} risk)
##            
##            Component Scores:
##            {format_components_for_prompt(mews_result['components'])}
##            
##            Provide a concise clinical interpretation:"""
##
##    #try:
##    #    ## [DEPRECATED]: Using Google GenAI client instead of Vertex AI directly
##    #    ## Initialize Vertex AI and the Gemini model
##    #    #vertexai.init(project=project_id, location=region)
##    #    #model = GenerativeModel("gemini-2.5-flash")
##    #    
##    #    #response = model.generate_content(prompt)
##    #    #return response.text
##
##    #    ## Migrate to Google GenAI client from Vertex AI
##    #    client = Client(
##    #        vertexai=True,
##    #        project=project_id,
##    #        location=region
##    #    )
##    #    response = client.models.generate_content(
##    #        model=MODEL_ID,
##    #        contents=prompt,
##    #    )
##    #    return response.text
##    
##    #except Exception as e:
##    #    return f"AI interpretation unavailable: {str(e)}"
##
##    for attempt in range(_max_retries):
##        try:
##            client = Client(
##                vertexai=True,
##                project=project_id,
##                location=region
##            )
##            response = client.models.generate_content(
##                model=MODEL_ID,
##                contents=prompt,
##            )
##            _last_ai_call = time.time()
##            return response.text
##        
##        except Exception as e:
##            if "429" in str(e) and attempt < _max_retries - 1:
##                wait_time = (attempt + 1) * 3  # 3s, 6s, 9s
##                time.sleep(wait_time)
##                continue
##            return f"AI interpretation unavailable: {str(e)}"
##    
##    return "AI interpretation unavailable: max retries exceeded"


def format_vitals_for_prompt(vitals: Dict[str, float]) -> str:
    """Format vitals dictionary for the AI prompt."""
    lines = []
    vital_labels = {
        'heart_rate': 'Heart Rate',
        'systolic_bp': 'Systolic BP',
        'diastolic_bp': 'Diastolic BP',
        'respiratory_rate': 'Respiratory Rate',
        'spo2': 'SpO2',
        'temperature_f': 'Temperature',
        'mean_arterial_pressure': 'MAP'
    }
    for key, value in vitals.items():
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
        'temperature_f': '°F'
    }
    return units.get(vital_type, '')


# Example usage
if __name__ == "__main__":
    # Test with sample vitals
    sample_vitals = {
        'heart_rate': 125,
        'systolic_bp': 85,
        'respiratory_rate': 24,
        'spo2': 93,
        'temperature_f': 101.5
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
