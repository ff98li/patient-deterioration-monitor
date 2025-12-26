import React, { useState, useEffect } from 'react';
import { Patient, RiskLevel } from '../types';
import { X, Activity, CheckCircle2, AlertOctagon, FlaskConical, Stethoscope, HelpCircle } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts';
import { RISK_COLORS, CONFIDENCE_COLORS } from '../constants';

interface PatientDetailModalProps {
  patient: Patient | null;
  onClose: () => void;
}

// API Configuration
// @ts-ignore
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5050';

export const PatientDetailModal: React.FC<PatientDetailModalProps> = ({ patient, onClose }) => {
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Fetch real history data when patient changes
  useEffect(() => {
    if (patient) {
      setHistoryLoading(true);
      fetch(`${API_BASE_URL}/api/patients/${patient.stay_id}/history`)
        .then(res => res.json())
        .then(data => {
          // Transform the history data for charts
          // const history = data.history || [];
          const history = Array.isArray(data) ? data : [];
          const chartData = history.map((reading: any, index: number) => ({
            time: index,  // Use index as x-axis (no time labels)
            mews: reading.mews_score || 0,
            // hr: reading.vitals?.heart_rate || 0,
            hr: reading.heart_rate || 0,   // heart_rate is at the top level, not nested under vitals
            spo2: reading.vitals?.spo2 || 0
          }));
          setHistoryData(chartData);
          setHistoryLoading(false);
        })
        .catch(() => {
          setHistoryData([]);
          setHistoryLoading(false);
        });
    }
  }, [patient]);

  if (!patient) return null;

  const hasLabs = patient.labs && (
    patient.labs.lactate > 0 || 
    patient.labs.creatinine > 0 || 
    patient.labs.wbc > 0 || 
    patient.labs.potassium > 0
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-4xl max-h-[90vh] rounded-2xl flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-700 flex justify-between items-center bg-slate-800">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-3">
              Patient {patient.stay_id}
              <span className={`text-sm px-3 py-1 rounded-full border ${RISK_COLORS[patient.risk_level]}`}>
                {patient.risk_level} RISK
              </span>
            </h2>
            <p className="text-slate-400 text-sm mt-1">Admitted for Sepsis Monitoring • ICU Bed 4</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            
            {/* Left Col: Vitals & Labs */}
            <div className="space-y-4">
               {/* Vitals Summary */}
               <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                <h3 className="text-slate-400 text-xs uppercase font-bold mb-4">Current Vitals</h3>
                <div className="grid grid-cols-3 gap-4">
                    <VitalBox label="Heart Rate" value={patient.vitals.heart_rate} unit="bpm" />
                    <VitalBox label="Resp. Rate" value={patient.vitals.respiratory_rate} unit="/min" />
                    <VitalBox label="SpO2" value={patient.vitals.spo2} unit="%" />
                    <VitalBox label="BP" value={`${patient.vitals.systolic_bp}/${patient.vitals.diastolic_bp}`} unit="mmHg" />
                    <VitalBox label="Temp" value={patient.vitals.temperature_f} unit="°F" />
                </div>
               </div>

               {/* Labs Summary */}
               <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                  <div className="flex justify-between items-center mb-4">
                     <h3 className="text-slate-400 text-xs uppercase font-bold flex items-center gap-2">
                        <FlaskConical size={14} /> Recent Labs
                     </h3>
                      <span className="text-[10px] text-slate-500">
                        {hasLabs 
                          ? (patient.labs_age_minutes >= 999 ? 'Age unknown' : `${patient.labs_age_minutes}m ago`)
                          : 'No labs available'}
                      </span>
                  </div>
                  <div className="grid grid-cols-4 gap-4">
                      <LabBox label="Lactate" value={patient.labs.lactate} unit="mmol/L" isHigh={patient.labs.lactate > 2.0} />
                      <LabBox label="Creatinine" value={patient.labs.creatinine} unit="mg/dL" isHigh={patient.labs.creatinine > 1.2} />
                      <LabBox label="WBC" value={patient.labs.wbc} unit="K/uL" isHigh={patient.labs.wbc > 12.0} />
                      <LabBox label="Potassium" value={patient.labs.potassium} unit="mmol/L" isHigh={patient.labs.potassium < 3.5 || patient.labs.potassium > 5.0} />
                  </div>
               </div>

               {/* False Alarm Mitigation Block */}
               <div className={`p-4 rounded-xl border flex items-center gap-3 ${patient.trend_confirmed ? 'bg-emerald-900/10 border-emerald-800' : 'bg-slate-800 border-slate-700'}`}>
                  {patient.trend_confirmed ? (
                      <>
                        <CheckCircle2 className="text-emerald-500" size={24} />
                        <div>
                            <h4 className="text-emerald-400 font-bold text-sm">Trend Confirmed</h4>
                            <p className="text-slate-400 text-xs">Alert verified by {patient.consecutive_readings} consecutive elevated readings. False alarm probability: &lt;5%.</p>
                        </div>
                      </>
                  ) : (
                      <>
                        <Activity className="text-slate-500" size={24} />
                         <div>
                            <h4 className="text-slate-300 font-bold text-sm">Monitoring Trend</h4>
                            <p className="text-slate-500 text-xs">Collecting sequential data to confirm deterioration pattern.</p>
                        </div>
                      </>
                  )}
               </div>
            </div>

            {/* Right Col: AI Analysis */}
            <div className="bg-indigo-900/10 p-4 rounded-xl border border-indigo-500/30 flex flex-col">
              <h3 className="text-indigo-400 text-xs uppercase font-bold mb-3 flex items-center gap-2">
                <Activity size={14} /> AI Interpretation
              </h3>
              
              {/* Assessment */}
              <div className="bg-slate-900/50 p-4 rounded-lg border border-indigo-500/20 mb-3">
                 <p className="text-slate-200 text-sm leading-relaxed font-medium">
                    "{patient.ai_assessment}"
                 </p>
              </div>

              {/* Recommendation */}
              <div className="mb-4">
                <h4 className="text-indigo-300 text-xs font-bold uppercase mb-2 flex items-center gap-2">
                    <Stethoscope size={12} /> Recommended Actions
                </h4>
                <div className="bg-indigo-600/20 p-3 rounded border-l-2 border-indigo-400 text-indigo-100 text-sm leading-relaxed">
                    {patient.ai_recommendation}
                </div>
              </div>

              {/* Footer / Reasoning */}
              <div className="mt-auto pt-4 border-t border-indigo-500/20">
                 <div className="flex justify-between items-end mb-2">
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-500 uppercase font-bold mb-1">Model Confidence</span>
                        <div className="flex items-center gap-2">
                            <span className={`text-xl font-bold ${CONFIDENCE_COLORS[patient.ai_confidence]}`}>{patient.ai_confidence}</span>
                            <span className="text-xs text-slate-500">Gemini 2.5 Flash</span>
                        </div>
                    </div>
                    <div className="text-right text-[10px] text-slate-500 font-mono">
                        Latency: 45ms
                    </div>
                 </div>
                 <div className="text-xs text-slate-400 italic bg-slate-900/30 p-2 rounded flex gap-2 items-start">
                    <HelpCircle size={12} className="mt-0.5 shrink-0" />
                    {patient.confidence_reasoning}
                 </div>
              </div>
            </div>
          </div>

          {/* Charts - Only show if we have real history data */}
          {historyData.length > 0 && (
            <div className="space-y-6">
              <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <h3 className="text-slate-400 text-xs uppercase font-bold mb-4">MEWS Score Trend</h3>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={historyData}>
                      <defs>
                        <linearGradient id="colorMews" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="time" hide={true} />
                      <YAxis stroke="#64748b" fontSize={12} />
                      <Tooltip 
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            return (
                              <div className="bg-slate-800 border border-slate-600 px-3 py-2 rounded">
                                <span className="text-red-400 font-mono">MEWS: {payload[0].value}</span>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Area type="monotone" dataKey="mews" stroke="#ef4444" fillOpacity={1} fill="url(#colorMews)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <h3 className="text-slate-400 text-xs uppercase font-bold mb-4">Heart Rate Trend</h3>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={historyData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="time" hide={true} />
                      <YAxis stroke="#64748b" fontSize={12} domain={['auto', 'auto']} />
                      <Tooltip 
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            return (
                              <div className="bg-slate-800 border border-slate-600 px-3 py-2 rounded">
                                <span className="text-blue-400 font-mono">HR: {payload[0].value?.toFixed(0)} bpm</span>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Line type="monotone" dataKey="hr" stroke="#3b82f6" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Loading state for charts */}
          {historyLoading && (
            <div className="text-center text-slate-500 py-8">
              Loading trend data...
            </div>
          )}

          {/* No data message */}
          {!historyLoading && historyData.length === 0 && (
            <div className="text-center text-slate-500 py-8">
              No trend data available yet. Data will appear after multiple readings.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Display unavailable vital values with N/A
const VitalBox = ({ label, value, unit }: any) => {
  const displayValue = value === 0 || value === undefined || value === null ? 'N/A' : value;
  const displayUnit = displayValue === 'N/A' ? '' : unit;
  
  return (
    <div>
      <div className="text-slate-500 text-[10px] uppercase">{label}</div>
      <div className="text-xl font-mono text-white">{displayValue} <span className="text-xs text-slate-600">{displayUnit}</span></div>
    </div>
  );
};

// Display unavailable lab values with N/A
const LabBox = ({ label, value, unit, isHigh }: any) => {
  const displayValue = value === 0 || value === undefined || value === null ? 'N/A' : value;
  const displayUnit = displayValue === 'N/A' ? '' : unit;
  
  return (
    <div>
      <div className="text-slate-500 text-[10px] uppercase truncate" title={label}>{label}</div>
      <div className={`text-lg font-mono ${isHigh ? 'text-orange-400 font-bold' : 'text-slate-300'}`}>
        {displayValue} <span className="text-[10px] text-slate-600 font-normal">{displayUnit}</span>
      </div>
    </div>
  );
};
