import { Patient, RiskLevel, ConfidenceLevel, Alert, DashboardStats } from '../types';

// Helper to generate random data
const randomInt = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1) + min);
const randomFloat = (min: number, max: number) => parseFloat((Math.random() * (max - min) + min).toFixed(1));

// Static list of base patients to simulate persistence
const BASE_PATIENTS = Array.from({ length: 15 }, (_, i) => ({
  stay_id: 30001446 + i,
  subject_id: 10001234 + i,
}));

export const generateMockData = (): { patients: Patient[], stats: DashboardStats, newAlert?: Alert } => {
  const now = new Date();
  
  const patients: Patient[] = BASE_PATIENTS.map(p => {
    // Determine risk mostly randomly but weighted
    const rand = Math.random();
    let risk = RiskLevel.NORMAL;
    let mews = randomInt(0, 2);
    
    if (rand > 0.95) { risk = RiskLevel.CRITICAL; mews = randomInt(7, 12); }
    else if (rand > 0.85) { risk = RiskLevel.HIGH; mews = randomInt(5, 6); }
    else if (rand > 0.70) { risk = RiskLevel.MEDIUM; mews = randomInt(3, 4); }
    else if (rand > 0.50) { risk = RiskLevel.LOW; mews = randomInt(1, 2); }

    // Correlate vitals to risk roughly
    const isCritical = risk === RiskLevel.CRITICAL || risk === RiskLevel.HIGH;
    
    // Generate Vitals
    const vitals = {
      heart_rate: isCritical ? randomInt(110, 160) : randomInt(60, 90),
      respiratory_rate: isCritical ? randomInt(25, 35) : randomInt(12, 18),
      spo2: isCritical ? randomInt(85, 92) : randomInt(95, 100),
      systolic_bp: isCritical ? randomInt(80, 100) : randomInt(110, 130),
      diastolic_bp: isCritical ? randomInt(40, 60) : randomInt(70, 85),
      temperature_f: isCritical ? randomFloat(101.5, 104) : randomFloat(97.5, 99.5),
    };

    // Generate Labs
    const labs = {
      lactate: isCritical ? randomFloat(2.5, 6.0) : randomFloat(0.5, 1.5),
      creatinine: randomFloat(0.6, 2.5),
      wbc: isCritical ? randomFloat(12.0, 20.0) : randomFloat(4.5, 10.0),
      potassium: randomFloat(3.0, 5.0),
    };

    // Generate AI content
    let assessment = "Patient stable. Vitals and labs within normal physiological limits. No acute distress noted.";
    let recommendation = "Continue routine monitoring per unit protocol.";
    let reasoning = "All physiological parameters are within baseline range.";

    if (risk === RiskLevel.CRITICAL) {
      assessment = `CRITICAL ALERT: Patient exhibits signs of uncompensated shock. Correlated elevation in Lactate (${labs.lactate} mmol/L) and HR (${vitals.heart_rate} bpm) suggests severe sepsis. Rapid response required.`;
      recommendation = "Initiate Sepsis Protocol Bundle immediately. Administer IV fluids (30ml/kg). Draw blood cultures before antibiotics. Consult intensivist.";
      reasoning = "Strong multi-modal correlation between hemodynamic instability (Hypotension) and inflammatory markers (Lactate > 4.0).";
    } else if (risk === RiskLevel.HIGH) {
      assessment = `WARNING: Hemodynamic instability detected. MEWS score escalated to ${mews}. Sustained tachycardia and hypotension indicate potential deterioration. Monitor fluid balance closely.`;
      recommendation = "Continuous vital monitoring q15min. Verify lactate levels. Assess fluid responsiveness. Prepare for potential escalation.";
      reasoning = "Consistent trend of rising HR and falling BP over last 3 windows. Confidence high due to signal quality.";
    } else if (risk === RiskLevel.MEDIUM) {
      assessment = `OBSERVATION: Early warning signs present. Slight elevation in inflammatory markers (WBC ${labs.wbc}). Recommended Action: Increase vital monitoring frequency.`;
      recommendation = "Increase monitoring frequency to q1h. Repeat Lactate and CBC in 4 hours. Monitor urine output.";
      reasoning = "Elevated WBC suggests infection, but hemodynamic stability lowers immediate risk prediction.";
    } else if (risk === RiskLevel.LOW) {
        reasoning = "Minor deviations in vitals detected but likely artifact or transient.";
    }

    const confidence = rand > 0.8 ? ConfidenceLevel.HIGH : (rand > 0.4 ? ConfidenceLevel.MEDIUM : ConfidenceLevel.LOW);
    // Add noise reasoning for low confidence
    if (confidence === ConfidenceLevel.LOW) {
        reasoning = "Prediction certainty reduced due to signal noise in SpO2 readings and missing recent lab values.";
    }

    const trendConfirmed = isCritical;
    const consecutiveReadings = isCritical ? randomInt(2, 5) : 1;

    return {
      ...p,
      mews_score: mews,
      risk_level: risk,
      vitals,
      labs,
      labs_age_minutes: randomInt(5, 240),
      sepsis_risk: isCritical ? (rand > 0.9 ? 'SEVERE' : 'MODERATE') : 'LOW',
      ai_confidence: confidence,
      last_updated: now.toISOString(),
      ai_assessment: assessment,
      trend_confirmed: trendConfirmed,
      consecutive_readings: consecutiveReadings,
      ai_recommendation: recommendation,
      confidence_reasoning: reasoning,
    };
  });

  // Sort: Critical first
  const riskOrder = { [RiskLevel.CRITICAL]: 0, [RiskLevel.HIGH]: 1, [RiskLevel.MEDIUM]: 2, [RiskLevel.LOW]: 3, [RiskLevel.NORMAL]: 4 };
  patients.sort((a, b) => riskOrder[a.risk_level] - riskOrder[b.risk_level]);

  // Generate a random alert occasionally
  let newAlert: Alert | undefined;
  if (Math.random() > 0.7) {
    const targetPatient = patients[randomInt(0, 4)]; // Pick one of the higher risk ones
    newAlert = {
      id: Math.random().toString(36).substr(2, 9),
      type: targetPatient.risk_level === RiskLevel.CRITICAL ? 'CRITICAL DETERIORATION' : 'SEPSIS WARNING',
      stay_id: targetPatient.stay_id,
      message: `${targetPatient.ai_assessment.substring(0, 80)}...`,
      timestamp: now.toISOString(),
      is_acknowledged: false,
      severity: targetPatient.risk_level === RiskLevel.CRITICAL ? 'critical' : 'warning',
    };
  }

  const stats: DashboardStats = {
    total_patients: 542, // Simulated total
    critical_count: patients.filter(p => p.risk_level === RiskLevel.CRITICAL).length,
    high_count: patients.filter(p => p.risk_level === RiskLevel.HIGH).length,
    alerts_today: 47 + randomInt(0, 5),
    stream_status: 'active',
    last_vitals_received: now.toISOString(),
  };

  return { patients, stats, newAlert };
};