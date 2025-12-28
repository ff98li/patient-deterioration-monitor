import React from 'react';
import { Patient, RiskLevel, ConfidenceLevel } from '../types';
import { RISK_COLORS, RISK_BADGE_COLORS, CONFIDENCE_COLORS, VITAL_ICONS } from '../constants';
import { AlertTriangle, Clock, FlaskConical, Brain, CheckCircle2 } from 'lucide-react';

interface PatientCardProps {
  patient: Patient;
  onClick: (patient: Patient) => void;
}

export const PatientCard: React.FC<PatientCardProps> = ({ patient, onClick }) => {
  const hasLabs = patient.labs && (
    patient.labs.lactate > 0 || 
    patient.labs.creatinine > 0 || 
    patient.labs.wbc > 0 || 
    patient.labs.potassium > 0
  );
  const isCritical = patient.risk_level === RiskLevel.CRITICAL;
  
  return (
    <div 
      onClick={() => onClick(patient)}
      className={`
        relative overflow-hidden rounded-lg mb-4 border-l-4 cursor-pointer transition-all hover:translate-x-1 hover:shadow-xl
        ${RISK_COLORS[patient.risk_level]}
        ${isCritical ? 'shadow-[0_0_15px_rgba(239,68,68,0.3)]' : 'bg-slate-800 border-slate-700'}
      `}
    >
      <div className="p-4">
        {/* Header Row */}
        <div className="flex justify-between items-start mb-3">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${RISK_BADGE_COLORS[patient.risk_level]}`}>
                {patient.risk_level}
              </span>
              <span className="text-lg font-mono font-semibold text-slate-100">
                Patient {patient.stay_id}
              </span>
              {patient.trend_confirmed && (
                <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400 bg-emerald-900/30 px-2 py-0.5 rounded border border-emerald-800">
                  <CheckCircle2 size={10} />
                  VERIFIED ({patient.consecutive_readings}/2)
                </span>
              )}
            </div>
            {patient.sepsis_risk !== 'LOW' && (
              <span className="flex items-center gap-1 text-xs font-bold text-red-400 w-fit">
                <AlertTriangle size={12} />
                SEPSIS RISK: {patient.sepsis_risk}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1 text-slate-400">
               <Clock size={12} />
               <span>2s ago</span>
            </div>
            <div className="flex items-center gap-1 bg-slate-900/50 px-2 py-1 rounded">
              <Brain size={12} className={CONFIDENCE_COLORS[patient.ai_confidence]} />
              <span className="text-slate-400">Confidence:</span>
              <span className={`font-bold ${CONFIDENCE_COLORS[patient.ai_confidence]}`}>
                {patient.ai_confidence}
              </span>
            </div>
            <div className="flex flex-col items-end">
              <span className="text-slate-400 uppercase text-[10px]">MEWS Score</span>
              <span className="text-2xl font-bold leading-none">{patient.mews_score}</span>
            </div>
          </div>
        </div>

        {/* Vitals Grid */}
        <div className="grid grid-cols-6 gap-2 mb-3 bg-slate-900/30 p-2 rounded-md">
          <VitalItem label="HR" value={patient.vitals.heart_rate} unit="bpm" icon={VITAL_ICONS.hr} risk={patient.vitals.heart_rate > 100 || patient.vitals.heart_rate < 50} />
          <VitalItem label="RR" value={patient.vitals.respiratory_rate} unit="/min" icon={VITAL_ICONS.rr} risk={patient.vitals.respiratory_rate > 20} />
          <VitalItem label="SpO2" value={patient.vitals.spo2} unit="%" icon={VITAL_ICONS.spo2} risk={patient.vitals.spo2 < 92} />
          <VitalItem label="BP" value={`${patient.vitals.systolic_bp}/${patient.vitals.diastolic_bp}`} unit="mmHg" icon={VITAL_ICONS.bp} risk={patient.vitals.systolic_bp < 90} />
          <VitalItem label="Temp" value={patient.vitals.temperature_c} unit="°C" icon={VITAL_ICONS.temp} risk={patient.vitals.temperature_c >= 38.5} />
        </div>

        {/* Labs Row */}
        {hasLabs && (
          <div className="flex items-center gap-4 text-xs text-slate-400 border-t border-slate-700/50 pt-2">
          <div className="flex items-center gap-2">
            <FlaskConical size={14} className="text-indigo-400" />
            <span className={patient.labs_age_minutes > 120 ? 'text-slate-500' : 'text-slate-300'}>
              Labs ({patient.labs_age_minutes}m ago):
            </span>
          </div>
          <LabItem label="Lac" value={patient.labs.lactate} unit="mmol/L" isHigh={patient.labs.lactate > 2.0} />
          <LabItem label="Cr" value={patient.labs.creatinine} unit="mg/dL" isHigh={patient.labs.creatinine > 1.2} />
          <LabItem label="WBC" value={patient.labs.wbc} unit="K/uL" isHigh={patient.labs.wbc > 12.0} />
          <LabItem label="K+" value={patient.labs.potassium} unit="mmol/L" isHigh={patient.labs.potassium < 3.5 || patient.labs.potassium > 5.0} />
          </div>
        )}
{/*         <div className="flex items-center gap-4 text-xs text-slate-400 border-t border-slate-700/50 pt-2">
          <div className="flex items-center gap-2">
            <FlaskConical size={14} className="text-indigo-400" />
            <span className={patient.labs_age_minutes > 120 ? 'text-slate-500' : 'text-slate-300'}>
              Labs ({patient.labs_age_minutes}m ago):
            </span>
          </div>
          <LabItem label="Lac" value={patient.labs.lactate} unit="mmol/L" isHigh={patient.labs.lactate > 2.0} />
          <LabItem label="Cr" value={patient.labs.creatinine} unit="mg/dL" isHigh={patient.labs.creatinine > 1.2} />
          <LabItem label="WBC" value={patient.labs.wbc} unit="K/uL" isHigh={patient.labs.wbc > 12.0} />
          <LabItem label="K+" value={patient.labs.potassium} unit="mmol/L" isHigh={patient.labs.potassium < 3.5 || patient.labs.potassium > 5.0} />
        </div> */}
      </div>
    </div>
  );
};

const VitalItem = ({ label, value, unit, icon: Icon, risk }: any) => {
  const displayValue = value === 0 || value === undefined || value === null ? 'N/A' : value;
  const displayUnit = displayValue === 'N/A' ? '' : unit;
  
  return (
    <div className="flex flex-col items-center justify-center p-1">
      <div className="flex items-center gap-1 text-[10px] text-slate-500 uppercase">
        <Icon size={10} /> {label}
      </div>
      <div className={`font-mono font-bold text-lg ${risk && displayValue !== 'N/A' ? 'text-red-400' : 'text-slate-200'}`}>
        {displayValue} <span className="text-[10px] font-normal text-slate-600 ml-[-2px]">{displayUnit}</span>
      </div>
    </div>
  );
};

const LabItem = ({ label, value, unit, isHigh }: any) => {
  const displayValue = value === 0 || value === undefined || value === null ? 'N/A' : value;
  const displayUnit = displayValue === 'N/A' ? '' : unit;
  
  return (
    <div className="flex gap-1 items-baseline">
      <span className="font-medium text-slate-500">{label}</span>
      <span className={`font-mono font-bold ${isHigh && displayValue !== 'N/A' ? 'text-orange-400' : 'text-slate-300'}`}>
        {displayValue}
      </span>
      <span className="text-[9px] text-slate-600">{displayUnit}</span>
    </div>
  );
};


/* const VitalItem = ({ label, value, unit, icon: Icon, risk }: any) => (
  <div className="flex flex-col items-center justify-center p-1">
    <div className="flex items-center gap-1 text-[10px] text-slate-500 uppercase">
      <Icon size={10} /> {label}
    </div>
    <div className={`font-mono font-bold text-lg ${risk ? 'text-red-400' : 'text-slate-200'}`}>
      {value} <span className="text-[10px] font-normal text-slate-600 ml-[-2px]">{unit}</span>
    </div>
  </div>
); */


/* const LabItem = ({ label, value, unit, isHigh }: any) => (
  <div className="flex gap-1 items-baseline">
    <span className="font-medium text-slate-500">{label}</span>
    <span className={`font-mono font-bold ${isHigh ? 'text-orange-400' : 'text-slate-300'}`}>
      {value}
    </span>
    <span className="text-[9px] text-slate-600">{unit}</span>
  </div>
); */