import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Patient, RiskLevel } from '../types';

interface RiskChartProps {
  patients: Patient[];
}

export const RiskChart: React.FC<RiskChartProps> = ({ patients }) => {
  const data = [
    { name: 'Normal', count: patients.filter(p => p.risk_level === RiskLevel.NORMAL).length, color: '#475569' },
    { name: 'Low', count: patients.filter(p => p.risk_level === RiskLevel.LOW).length, color: '#059669' },
    { name: 'Medium', count: patients.filter(p => p.risk_level === RiskLevel.MEDIUM).length, color: '#d97706' },
    { name: 'High', count: patients.filter(p => p.risk_level === RiskLevel.HIGH).length, color: '#ea580c' },
    { name: 'Critical', count: patients.filter(p => p.risk_level === RiskLevel.CRITICAL).length, color: '#dc2626' },
  ];

  return (
    <div className="h-32 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey="name" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
          <YAxis stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
          <Tooltip 
            cursor={{fill: '#334155', opacity: 0.2}}
            contentStyle={{ backgroundColor: '#1e293b', borderColor: '#475569', color: '#f1f5f9', borderRadius: '8px' }}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};