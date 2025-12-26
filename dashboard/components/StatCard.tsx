import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  colorClass: string;
  subtext?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, colorClass, subtext }) => {
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700 shadow-lg flex flex-col justify-between">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider">{title}</h3>
          <div className={`mt-2 text-3xl font-bold ${colorClass}`}>
            {value}
          </div>
        </div>
        <div className={`p-3 rounded-lg bg-slate-900/50 ${colorClass}`}>
          <Icon size={24} />
        </div>
      </div>
      {subtext && (
        <div className="mt-4 text-xs text-slate-500">
          {subtext}
        </div>
      )}
    </div>
  );
};
