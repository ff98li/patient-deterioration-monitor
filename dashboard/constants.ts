import { RiskLevel, ConfidenceLevel } from './types';
import { Activity, Thermometer, Wind, Droplets, Heart } from 'lucide-react';

export const RISK_COLORS = {
  [RiskLevel.NORMAL]: 'bg-slate-700 text-slate-300 border-slate-600',
  [RiskLevel.LOW]: 'bg-emerald-900/30 text-emerald-400 border-emerald-800',
  [RiskLevel.MEDIUM]: 'bg-yellow-900/30 text-yellow-400 border-yellow-700',
  [RiskLevel.HIGH]: 'bg-orange-900/30 text-orange-400 border-orange-600',
  [RiskLevel.CRITICAL]: 'bg-red-900/40 text-red-400 border-red-600 animate-pulse-slow',
};

export const RISK_BADGE_COLORS = {
  [RiskLevel.NORMAL]: 'bg-slate-600 text-slate-100',
  [RiskLevel.LOW]: 'bg-emerald-600 text-white',
  [RiskLevel.MEDIUM]: 'bg-yellow-600 text-white',
  [RiskLevel.HIGH]: 'bg-orange-600 text-white',
  [RiskLevel.CRITICAL]: 'bg-red-600 text-white',
};

export const CONFIDENCE_COLORS = {
  [ConfidenceLevel.HIGH]: 'text-emerald-400',
  [ConfidenceLevel.MEDIUM]: 'text-yellow-400',
  [ConfidenceLevel.LOW]: 'text-red-400',
};

export const VITAL_ICONS = {
  hr: Heart,
  rr: Wind,
  spo2: Activity,
  bp: Droplets,
  temp: Thermometer
};
