export enum RiskLevel {
  NORMAL = 'NORMAL',
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

export enum ConfidenceLevel {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
}

export interface Vitals {
  heart_rate: number;
  respiratory_rate: number;
  spo2: number;
  systolic_bp: number;
  diastolic_bp: number;
  temperature_f: number;
}

export interface Labs {
  lactate: number;
  creatinine: number;
  wbc: number;
  potassium: number;
}

export interface Patient {
  stay_id: number;
  subject_id: number;
  mews_score: number;
  risk_level: RiskLevel;
  vitals: Vitals;
  labs: Labs;
  labs_age_minutes: number;
  sepsis_risk: string; // 'LOW' | 'MODERATE' | 'SEVERE'
  ai_confidence: ConfidenceLevel;
  last_updated: string;
  // New fields for dashboard enhancement
  ai_assessment: string;
  trend_confirmed: boolean;
  consecutive_readings: number;
  ai_recommendation: string;
  confidence_reasoning: string;
}

export interface Alert {
  id: string;
  type: string;
  stay_id: number;
  message: string;
  timestamp: string;
  is_acknowledged: boolean;
  severity: 'info' | 'warning' | 'critical';
}

export interface DashboardStats {
  total_patients: number;
  critical_count: number;
  high_count: number;
  alerts_today: number;
  stream_status: 'active' | 'inactive';
  last_vitals_received: string;
}