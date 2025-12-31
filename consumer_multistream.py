"""
Multi-Stream Consumer: Joins patient vitals and lab streams for comprehensive analysis

This script consumes vital signs and lab results from two Kafka topics,
joins them by patient (stay_id), and runs combined deterioration predictions.

This demonstrates Confluent Kafka's multi-stream processing capability.
"""

import json
from datetime import datetime, UTC, timedelta
from collections import defaultdict
from confluent_kafka import Consumer, KafkaError
from typing import Dict, List, Optional
import threading
import time

import config
from model import calculate_mews_score, get_ai_interpretation
from lab_analysis import analyze_labs, check_sepsis_indicators, format_labs_for_display, format_labs_for_ai
import shared_state


# Topics
VITALS_TOPIC = config.KAFKA_TOPIC  # "patient-vitals"
LABS_TOPIC = "patient-labs"

# In-memory storage
alerts: List[Dict] = []
patient_vitals_history: Dict[int, List[Dict]] = defaultdict(list)
patient_labs_history: Dict[int, List[Dict]] = defaultdict(list)
patient_latest_labs: Dict[int, Dict] = {}  # Most recent labs per patient

# Alert confirmation tracking
pending_alerts = defaultdict(lambda: {
    'first_triggered': None,
    'trigger_count': 0,
    'last_mews': 0,
    'confirmed': False
})

# ============================================================
# AI THROTTLING - Reduce Vertex AI API costs
# ============================================================
_ai_call_timestamps: Dict[int, datetime] = {}  # stay_id -> last AI call time
AI_COOLDOWN_SECONDS = 300  # 5 minutes between AI calls per patient

def should_call_ai(stay_id: int) -> bool:
    """
    Rate limit AI calls per patient to reduce API costs.
    Returns True if enough time has passed since last AI call for this patient.
    """
    now = datetime.now(UTC)
    last_call = _ai_call_timestamps.get(stay_id)
    
    if last_call is None:
        _ai_call_timestamps[stay_id] = now
        return True
    
    time_since_last = (now - last_call).total_seconds()
    if time_since_last >= AI_COOLDOWN_SECONDS:
        _ai_call_timestamps[stay_id] = now
        return True
    
    return False

def get_ai_cooldown_remaining(stay_id: int) -> int:
    """Get seconds remaining until AI can be called again for this patient."""
    last_call = _ai_call_timestamps.get(stay_id)
    if last_call is None:
        return 0
    elapsed = (datetime.now(UTC) - last_call).total_seconds()
    remaining = AI_COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining))
# ============================================================

# Configuration
ALERT_CONFIRMATION_COUNT = 2
ALERT_CONFIRMATION_WINDOW_SECONDS = 300
LAB_STALENESS_MINUTES = 240  # Labs older than 4 hours are considered stale


def check_alert_confirmation(stay_id: str, current_mews: int, risk_level: str) -> dict:
    """Check if an alert should be confirmed based on trend."""
    now = datetime.now(UTC)
    alert_state = pending_alerts[stay_id]
    
    is_elevated = risk_level in ['MEDIUM', 'HIGH', 'CRITICAL']
    
    if not is_elevated:
        if alert_state['first_triggered'] is not None:
            pending_alerts[stay_id] = {
                'first_triggered': None,
                'trigger_count': 0,
                'last_mews': 0,
                'confirmed': False
            }
        return {
            'should_alert': False,
            'status': 'NORMAL',
            'details': 'Patient vitals within acceptable range'
        }
    
    if alert_state['confirmed'] and alert_state['last_mews'] <= current_mews:
        return {
            'should_alert': False,
            'status': 'ALREADY_ALERTED',
            'details': f'Alert already confirmed (MEWS: {current_mews})'
        }
    
    if alert_state['first_triggered'] is None:
        pending_alerts[stay_id] = {
            'first_triggered': now,
            'trigger_count': 1,
            'last_mews': current_mews,
            'confirmed': False
        }
        return {
            'should_alert': False,
            'status': 'PENDING',
            'details': f'Elevated reading detected (1/{ALERT_CONFIRMATION_COUNT}), awaiting confirmation'
        }
    
    time_since_first = (now - alert_state['first_triggered']).total_seconds()
    
    if time_since_first > ALERT_CONFIRMATION_WINDOW_SECONDS:
        pending_alerts[stay_id] = {
            'first_triggered': now,
            'trigger_count': 1,
            'last_mews': current_mews,
            'confirmed': False
        }
        return {
            'should_alert': False,
            'status': 'PENDING',
            'details': f'New elevated reading (previous window expired)'
        }
    
    alert_state['trigger_count'] += 1
    alert_state['last_mews'] = current_mews
    
    if alert_state['trigger_count'] >= ALERT_CONFIRMATION_COUNT:
        alert_state['confirmed'] = True
        return {
            'should_alert': True,
            'status': 'CONFIRMED',
            'details': f'Alert confirmed: {alert_state["trigger_count"]} consecutive elevated readings in {time_since_first:.0f}s'
        }
    else:
        return {
            'should_alert': False,
            'status': 'PENDING',
            'details': f'Elevated reading ({alert_state["trigger_count"]}/{ALERT_CONFIRMATION_COUNT}), awaiting confirmation'
        }


def create_consumer(group_id: str = 'patient-monitoring-multistream'):
    """Create and configure Kafka consumer for both topics."""
    conf = {
        'bootstrap.servers': config.CONFLUENT_BOOTSTRAP_SERVER,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': config.CONFLUENT_API_KEY,
        'sasl.password': config.CONFLUENT_API_SECRET,
        'group.id': group_id,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': True,
    }
    return Consumer(conf)


def process_vitals_message(data: Dict) -> Dict:
    """Process a vital signs message."""
    stay_id = data['stay_id']
    vitals = data['vitals']
    timestamp = data['timestamp']
    
    # Calculate MEWS score
    mews_result = calculate_mews_score(vitals)
    
    result = {
        'subject_id': data['subject_id'],
        'stay_id': stay_id,
        'timestamp': timestamp,
        'vitals': vitals,
        'mews_score': mews_result['mews_total'],
        'risk_level': mews_result['risk_level'],
        'risk_score': mews_result['risk_score'],
        'components': mews_result['components'],
        'processed_at': datetime.now(UTC).isoformat(),
        'type': 'vitals'
    }
    
    # Store in history
    patient_vitals_history[stay_id].append(result)
    if len(patient_vitals_history[stay_id]) > 50:
        patient_vitals_history[stay_id] = patient_vitals_history[stay_id][-50:]
    
    # Update shared state
    shared_state.update_patient(stay_id, result)
    
    return result


def process_labs_message(data: Dict) -> Dict:
    """Process a lab results message."""
    print(f"🧪 DEBUG: process_labs_message called for {data['stay_id']}")
    stay_id = data['stay_id']
    labs = data['labs']
    units = data.get('units', {})
    timestamp = data['timestamp']
    
    # Analyze lab results
    lab_analysis = analyze_labs(labs)
    
    result = {
        'subject_id': data['subject_id'],
        'stay_id': stay_id,
        'timestamp': timestamp,
        'labs': labs,
        'units': units,
        'lab_analysis': lab_analysis,
        'processed_at': datetime.now(UTC).isoformat(),
        'type': 'labs'
    }
    
    # Store in history and update latest
    patient_labs_history[stay_id].append(result)
    if len(patient_labs_history[stay_id]) > 20:
        patient_labs_history[stay_id] = patient_labs_history[stay_id][-20:]
    
    patient_latest_labs[stay_id] = result

    # UPDATE: send labs to shared state for dashboard
    shared_state.update_patient_labs(stay_id, {
        'labs': labs,
        'labs_age_minutes': 0  # Fresh labs
    })
    print(f"📊 DEBUG: Updating labs for {stay_id}: {labs}")
    
    return result


def get_combined_analysis(stay_id: int, vitals_result: Dict) -> Dict:
    """
    Combine vitals with most recent labs for comprehensive analysis.
    This is the multi-stream JOIN operation.
    """
    latest_labs = patient_latest_labs.get(stay_id)
    
    combined = {
        'vitals': vitals_result,
        'labs': None,
        'labs_age_minutes': None,
        'sepsis_check': None,
        'combined_risk': vitals_result['risk_level']
    }
    
    if latest_labs:
        # Calculate lab staleness
        vitals_time = datetime.fromisoformat(vitals_result['timestamp'].replace('Z', '+00:00'))
        labs_time = datetime.fromisoformat(latest_labs['timestamp'].replace('Z', '+00:00'))
        labs_age = (vitals_time - labs_time).total_seconds() / 60
        
        combined['labs'] = latest_labs
        combined['labs_age_minutes'] = labs_age
        
        # Only use labs if not too stale
        if labs_age <= LAB_STALENESS_MINUTES:
            # Check sepsis indicators with combined data
            sepsis_check = check_sepsis_indicators(
                latest_labs['labs'],
                vitals_result['vitals']
            )
            combined['sepsis_check'] = sepsis_check
            
            # Elevate risk if sepsis indicators present
            lab_risk = latest_labs['lab_analysis']['risk_level']
            vitals_risk = vitals_result['risk_level']
            
            risk_order = ['NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            vitals_idx = risk_order.index(vitals_risk) if vitals_risk in risk_order else 0
            lab_idx = risk_order.index(lab_risk) if lab_risk in risk_order else 0
            sepsis_idx = risk_order.index(sepsis_check['sepsis_risk']) if sepsis_check['sepsis_risk'] in risk_order else 0
            
            combined['combined_risk'] = risk_order[max(vitals_idx, lab_idx, sepsis_idx)]
    
    return combined


def get_ai_interpretation_with_labs(
    vitals: Dict[str, float],
    mews_result: Dict,
    labs: Optional[Dict] = None,
    labs_age_minutes: Optional[float] = None,
    sepsis_check: Optional[Dict] = None,
    project_id: str = None,
    region: str = "us-central1"
) -> Dict[str, str]:
    """
    Get AI interpretation with combined vitals and labs context.
    """
    from model import format_vitals_for_prompt, format_components_for_prompt, _last_ai_call, MIN_AI_INTERVAL, MODEL_ID
    from google import genai
    from google.genai import Client
    import time as time_module
    
    #global _last_ai_call
    
    # Build prompt with labs context
    labs_section = ""
    if labs:
        labs_section = f"""
Lab Results (collected {labs_age_minutes:.0f} minutes ago):
{format_labs_for_ai(labs.get('labs', {}), labs.get('units', {}))}

Lab Analysis: {labs.get('lab_analysis', {}).get('risk_level', 'N/A')} risk
Abnormal labs: {', '.join(labs.get('lab_analysis', {}).get('abnormal_labs', [])) or 'None'}
"""
    
    sepsis_section = ""
    if sepsis_check:
        sepsis_section = f"""
Sepsis Screening:
  Risk Level: {sepsis_check['sepsis_risk']}
  Score: {sepsis_check['sepsis_score']}
  Indicators: {', '.join(sepsis_check['indicators']) or 'None'}
"""
    
    # Count available data for confidence
    available_vitals = [k for k, v in vitals.items() if v is not None]
    has_labs = labs is not None and labs_age_minutes and labs_age_minutes <= LAB_STALENESS_MINUTES
    
    prompt = f"""You are a clinical decision support assistant analyzing patient data.

VITAL SIGNS:
{format_vitals_for_prompt(vitals)}

MEWS Score: {mews_result.get('mews_total', 'N/A')} ({mews_result.get('risk_level', 'N/A')} risk)
{labs_section}
{sepsis_section}

Data completeness: {len(available_vitals)}/7 vitals, Labs: {'Available' if has_labs else 'Not available'}

Respond in this EXACT JSON format (no markdown, no code blocks):
{{
    "interpretation": "2-3 sentence clinical interpretation integrating vitals{' and labs' if has_labs else ''}. Highlight any concerning patterns or correlations.",
    "confidence": "LOW|MEDIUM|HIGH",
    "confidence_reasoning": "Brief explanation of confidence based on data completeness and clinical clarity",
    "priority_concerns": ["List", "of", "top", "concerns"],
    "recommended_actions": ["List", "of", "suggested", "actions"]
}}

Confidence guidelines:
- HIGH: Complete vitals AND recent labs, clear clinical picture
- MEDIUM: Most vitals available, labs may be missing or stale
- LOW: Missing key vitals, no labs, or conflicting signals"""

    try:
        client = Client(
            vertexai=True,
            project=project_id or config.GCP_PROJECT_ID,
            location=region
        )
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        import json as json_module
        result = json_module.loads(response_text)
        return result
        
    except Exception as e:
        return {
            "interpretation": f"AI interpretation unavailable: {str(e)}",
            "confidence": "UNKNOWN",
            "confidence_reasoning": "API error",
            "priority_concerns": [],
            "recommended_actions": []
        }


def display_vitals_result(result: Dict, combined: Dict = None):
    """Display vitals processing result."""
    risk_emoji = {
        'NORMAL': '🟢', 'LOW': '🟡', 'MEDIUM': '🟠', 'HIGH': '🔴', 'CRITICAL': '🚨'
    }
    
    emoji = risk_emoji.get(result['risk_level'], '⚪')
    vitals = result['vitals']
    vitals_str = " | ".join([f"{k[:3].upper()}:{v:.0f}" for k, v in vitals.items() if v is not None])
    
    print(f"{emoji} Stay:{result['stay_id']} | MEWS:{result['mews_score']} | {result['risk_level']}")
    print(f"   Vitals: {vitals_str}")
    
    # Show labs summary if available
    if combined and combined.get('labs'):
        labs_age = combined.get('labs_age_minutes', 0)
        labs = combined['labs']['labs']
        labs_str = format_labs_for_display(labs)
        stale_marker = " ⏰" if labs_age > LAB_STALENESS_MINUTES else ""
        print(f"   Labs ({labs_age:.0f}m ago{stale_marker}): {labs_str}")
        
        if combined.get('sepsis_check'):
            sepsis = combined['sepsis_check']
            if sepsis['sepsis_risk'] in ['MODERATE', 'HIGH']:
                print(f"   ⚠️  Sepsis Risk: {sepsis['sepsis_risk']} - {sepsis['recommendation']}")


def display_labs_result(result: Dict):
    """Display lab processing result."""
    risk_emoji = {
        'NORMAL': '🟢', 'LOW': '🟡', 'MEDIUM': '🟠', 'HIGH': '🔴', 'CRITICAL': '🚨'
    }
    
    analysis = result['lab_analysis']
    emoji = risk_emoji.get(analysis['risk_level'], '⚪')
    labs_str = format_labs_for_display(result['labs'], result.get('units', {}))
    
    print(f"🧪 Stay:{result['stay_id']} | Lab Risk: {analysis['risk_level']}")
    print(f"   Labs: {labs_str}")
    
    if analysis['abnormal_labs']:
        print(f"   ⚠️  Abnormal: {', '.join(analysis['abnormal_labs'][:3])}")


def display_alert_with_labs(alert: dict, vitals: dict, mews_result: dict, 
                            combined: dict, confirmation_info: dict = None):
    """Display alert with AI interpretation including labs."""
    print("\n" + "!" * 70)
    print(f"🚨 ALERT: {alert['type']}")
    print(f"   Patient {alert['stay_id']} - {alert['message']}")
    
    if confirmation_info:
        status_emoji = {'CONFIRMED': '✅', 'PENDING': '⏳', 'ALREADY_ALERTED': '📝'}.get(
            confirmation_info.get('status', ''), '❓')
        print(f"   {status_emoji} Status: {confirmation_info.get('details', 'Unknown')}")
    
    vitals_str = " | ".join([f"{k[:3].upper()}:{v:.1f}" for k, v in vitals.items() if v is not None])
    print(f"   Vitals: {vitals_str}")
    
    # Show labs if available
    if combined.get('labs'):
        labs = combined['labs']['labs']
        labs_str = format_labs_for_display(labs)
        print(f"   Labs: {labs_str}")
        
        if combined.get('sepsis_check') and combined['sepsis_check']['sepsis_risk'] != 'MINIMAL':
            sepsis = combined['sepsis_check']
            print(f"   🦠 Sepsis Risk: {sepsis['sepsis_risk']} (score: {sepsis['sepsis_score']})")
    
    print("!" * 70)
    
    # Get AI interpretation with labs context - WITH THROTTLING
    stay_id = alert['stay_id']
    if alert['severity'] in ['HIGH', 'CRITICAL']:
        if should_call_ai(stay_id):
            print(f"  🤖 Calling AI for patient {stay_id}...")
            ai_result = get_ai_interpretation_with_labs(
                vitals,
                mews_result,
                labs=combined.get('labs'),
                labs_age_minutes=combined.get('labs_age_minutes'),
                sepsis_check=combined.get('sepsis_check'),
                project_id=config.GCP_PROJECT_ID,
                region=config.GCP_REGION
            )
            
            confidence = ai_result.get('confidence', 'UNKNOWN')
            confidence_emoji = {'HIGH': '🟢', 'MEDIUM': '🟡', 'LOW': '🔴', 'UNKNOWN': '⚪'}.get(confidence, '⚪')
            
            print(f"\n  🤖 AI Assessment (Confidence: {confidence_emoji} {confidence}):")
            print(f"     {ai_result.get('interpretation', 'No interpretation available')}")
            
            shared_state.update_patient_ai(alert['stay_id'], ai_result)

            if ai_result.get('priority_concerns'):
                print(f"     📋 Concerns: {', '.join(ai_result['priority_concerns'][:3])}")
            
            if ai_result.get('recommended_actions'):
                print(f"     💊 Actions: {', '.join(ai_result['recommended_actions'][:2])}")
            
            if confidence in ['LOW', 'MEDIUM']:
                print(f"     ⚠️  {ai_result.get('confidence_reasoning', '')}")
        else:
            cooldown = get_ai_cooldown_remaining(stay_id)
            print(f"\n  ⏳ AI throttled for patient {stay_id} (cooldown: {cooldown}s remaining)")
            print(f"     Using previous assessment. Next AI call in {cooldown}s.")
    
    print()


def consume_multistream(consumer: Consumer):
    """Main consumption loop for both vitals and labs topics."""
    consumer.subscribe([VITALS_TOPIC, LABS_TOPIC])
    
    print(f"\n👂 Listening for data on topics: {VITALS_TOPIC}, {LABS_TOPIC}")
    print(f"   Alert threshold: {config.ALERT_THRESHOLD}")
    print(f"   Lab staleness threshold: {LAB_STALENESS_MINUTES} minutes")
    print(f"   AI cooldown per patient: {AI_COOLDOWN_SECONDS} seconds")
    print("-" * 70)
    
    vitals_count = 0
    labs_count = 0
    alert_count = 0
    ai_calls_saved = 0
    
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(f"❌ Error: {msg.error()}")
                    continue
            
            topic = msg.topic()
            
            try:
                data = json.loads(msg.value().decode('utf-8'))
                
                if topic == VITALS_TOPIC:
                    # Process vitals
                    result = process_vitals_message(data)
                    vitals_count += 1
                    
                    # Get combined analysis with labs
                    combined = get_combined_analysis(result['stay_id'], result)
                    
                    # Display result
                    display_vitals_result(result, combined)
                    
                    # Check for alerts with confirmation
                    stay_id = result['stay_id']
                    mews_score = result['mews_score']
                    risk_level = combined['combined_risk']  # Use combined risk
                    vitals = result['vitals']
                    mews_result = {
                        'mews_total': mews_score,
                        'risk_level': result['risk_level'],
                        'components': result['components']
                    }
                    
                    confirmation = check_alert_confirmation(stay_id, mews_score, risk_level)

                    # UPDATE: send alert confirmation status to shared state for dashboard
                    shared_state.update_patient_alert_status(
                        stay_id,
                        confirmation['status'] == 'CONFIRMED' or pending_alerts[stay_id].get('confirmed', False),
                        pending_alerts[stay_id].get('trigger_count', 0)
                    )
                    
                    # Generate alerts
                    if risk_level in ['HIGH', 'CRITICAL'] and confirmation['should_alert']:
                        alert = {
                            'type': 'HIGH_RISK',
                            'stay_id': stay_id,
                            'subject_id': result['subject_id'],
                            'severity': risk_level,
                            'mews_score': mews_score,
                            'vitals': vitals,
                            'has_labs': combined.get('labs') is not None,
                            #'message': f"MEWS score {mews_score} indicates {risk_level} risk",
                            'message': f"Combined assessment: {risk_level} risk (MEWS: {mews_score})",
                            'timestamp': result['timestamp'],
                            'triggered_at': datetime.now(UTC).isoformat()
                        }
                        
                        alerts.append(alert)
                        alert_count += 1
                        shared_state.add_alert(alert)
                        display_alert_with_labs(alert, vitals, mews_result, combined, confirmation)
                    
                    
                    
                    # Log pending
                    if confirmation['status'] == 'PENDING':
                        print(f"  ⏳ {stay_id}: {confirmation['details']}")
                
                elif topic == LABS_TOPIC:
                    # Process labs
                    result = process_labs_message(data)
                    labs_count += 1
                    display_labs_result(result)
                    
                    # Check for critical lab alerts
                    analysis = result['lab_analysis']
                    if analysis['risk_level'] == 'CRITICAL':
                        print(f"\n🚨 CRITICAL LAB ALERT: Patient {result['stay_id']}")
                        for alert_item in analysis['alerts']:
                            print(f"   ⚠️  {alert_item['lab']}: {alert_item['value']} ({alert_item['status']})")
                
                # Periodic summary
                if (vitals_count + labs_count) % 100 == 0:
                    print(f"\n📊 Processed {vitals_count} vitals, {labs_count} labs, {alert_count} alerts\n")
                    
            except Exception as e:
                print(f"❌ Error processing message: {e}")
                import traceback
                traceback.print_exc()
                
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        consumer.close()
        print(f"\n📊 Final Summary:")
        print(f"   Vitals processed: {vitals_count}")
        print(f"   Labs processed: {labs_count}")
        print(f"   Alerts triggered: {alert_count}")
        print(f"   Patients monitored: {len(set(patient_vitals_history.keys()) | set(patient_labs_history.keys()))}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Patient Deterioration Monitor - Multi-Stream Consumer")
    print("Consuming: Vitals + Labs | Demonstrating Confluent Stream Joins")
    print("=" * 70)
    
    consumer = create_consumer()
    print(f"\n✓ Connected to Confluent Cloud")
    print(f"  Server: {config.CONFLUENT_BOOTSTRAP_SERVER}")
    
    consume_multistream(consumer)


if __name__ == "__main__":
    main()
