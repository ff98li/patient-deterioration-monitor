import { Patient, Alert, DashboardStats } from '../types';

// API Configuration
// @ts-ignore
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5050';

interface DashboardData {
  patients: Patient[];
  alerts: Alert[];
  stats: DashboardStats;
}

/**
 * Fetch all dashboard data from the backend API
 */
export const fetchDashboardData = async (): Promise<DashboardData> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/data`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Transform backend data to match frontend types if needed
    return {
      patients: data.patients.map(transformPatient),
      alerts: data.alerts || [],
      stats: {
        total_patients: data.stats?.total_patients || 0,
        critical_count: data.stats?.critical_count || 0,
        high_count: data.stats?.high_count || 0,
        alerts_today: data.stats?.alerts_today || 0,
        stream_status: data.stats?.stream_status || 'inactive',
        last_vitals_received: data.stats?.last_vitals_received || new Date().toISOString(),
      }
    };
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error);
    throw error;
  }
};

/**
 * Fetch patient history for trend charts
 */
export const fetchPatientHistory = async (stayId: number): Promise<any[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/patients/${stayId}/history`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch patient history:', error);
    return [];
  }
};

/**
 * Acknowledge an alert
 */
export const acknowledgeAlert = async (alertId: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    return response.ok;
  } catch (error) {
    console.error('Failed to acknowledge alert:', error);
    return false;
  }
};

/**
 * Transform backend patient data to frontend format
 * Handles any field name differences or missing data
 */
const transformPatient = (backendPatient: any): Patient => {
  return {
    stay_id: backendPatient.stay_id,
    subject_id: backendPatient.subject_id,
    mews_score: backendPatient.mews_score || 0,
    risk_level: backendPatient.risk_level || 'NORMAL',
    
    vitals: {
      heart_rate: backendPatient.vitals?.heart_rate || 0,
      respiratory_rate: backendPatient.vitals?.respiratory_rate || 0,
      spo2: backendPatient.vitals?.spo2 || 0,
      systolic_bp: backendPatient.vitals?.systolic_bp || 0,
      diastolic_bp: backendPatient.vitals?.diastolic_bp || 0,
      temperature_f: backendPatient.vitals?.temperature_f || 0,
    },
    
    labs: {
      lactate: backendPatient.labs?.lactate || 0,
      creatinine: backendPatient.labs?.creatinine || 0,
      wbc: backendPatient.labs?.wbc || 0,
      potassium: backendPatient.labs?.potassium || 0,
    },
    
    labs_age_minutes: backendPatient.labs_age_minutes ?? 999,
    sepsis_risk: backendPatient.sepsis_risk || 'LOW',
    ai_confidence: backendPatient.ai_confidence || 'MEDIUM',
    last_updated: backendPatient.last_updated || new Date().toISOString(),
    
    // AI interpretation fields
    ai_assessment: backendPatient.ai_assessment || 'Awaiting assessment...',
    ai_recommendation: backendPatient.ai_recommendation || 'Continue monitoring.',
    confidence_reasoning: backendPatient.confidence_reasoning || '',
    
    // Alert confirmation
    trend_confirmed: backendPatient.trend_confirmed || false,
    consecutive_readings: backendPatient.consecutive_readings || 0,
  };
};

/**
 * Check if the API is available
 */
export const checkApiHealth = async (): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/`, { 
      method: 'GET',
      // Short timeout for health check
      signal: AbortSignal.timeout(3000),
    });
    return response.ok;
  } catch {
    return false;
  }
};
