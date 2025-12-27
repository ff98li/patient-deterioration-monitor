import React, { useState } from 'react';
import { Alert, Patient } from '../types';
import { Bell, CheckCircle, AlertTriangle, AlertOctagon, ArrowRight, Filter } from 'lucide-react';

interface AlertFeedProps {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
  onSelectPatient: (stayId: number) => void;
}

export const AlertFeed: React.FC<AlertFeedProps> = ({ alerts, onAcknowledge, onSelectPatient }) => {
  const [showOnlyUnacked, setShowOnlyUnacked] = useState(false);

  const filteredAlerts = showOnlyUnacked 
    ? alerts.filter(a => !a.is_acknowledged)
    : alerts;

  const unackedCount = alerts.filter(a => !a.is_acknowledged).length;

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 h-full flex flex-col">
      <div className="p-4 border-b border-slate-700 flex justify-between items-center">
        <h3 className="font-semibold text-slate-100 flex items-center gap-2">
          <Bell size={18} />
          Alert Feed
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowOnlyUnacked(!showOnlyUnacked)}
            className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border transition-colors ${
              showOnlyUnacked
                ? 'bg-red-900/50 border-red-700 text-red-300'
                : 'bg-slate-700 border-slate-600 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Filter size={12} />
            {showOnlyUnacked ? 'Unacked Only' : 'All'}
          </button>
          <span className="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
            {unackedCount} New
          </span>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {filteredAlerts.length === 0 ? (
          <div className="text-center text-slate-500 py-10 text-sm">
            {showOnlyUnacked ? 'No unacknowledged alerts' : 'No active alerts'}
          </div>
        ) : (
          filteredAlerts.map(alert => (
            <div 
              key={alert.id}
              className={`
                relative p-3 rounded-lg border text-sm transition-all duration-300
                ${alert.is_acknowledged ? 'opacity-50 grayscale bg-slate-900 border-slate-800' : 'bg-slate-900/50 border-slate-700'}
                ${!alert.is_acknowledged && alert.severity === 'critical' ? 'border-red-500/50 shadow-[0_0_10px_rgba(239,68,68,0.1)]' : ''}
              `}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  {alert.severity === 'critical' ? (
                    <AlertOctagon size={16} className="text-red-500" />
                  ) : (
                    <AlertTriangle size={16} className="text-orange-400" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex justify-between items-start mb-1">
                    <span className={`font-bold text-xs uppercase ${alert.severity === 'critical' ? 'text-red-400' : 'text-orange-300'}`}>
                      {alert.type}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="text-slate-300 font-medium mb-1">
                    Patient {alert.stay_id}
                  </div>
                  <p className="text-slate-400 text-xs leading-relaxed line-clamp-2">
                    {alert.message}
                  </p>
                  
                  <div className="flex gap-2 mt-3">
                    {!alert.is_acknowledged && (
                        <button 
                        onClick={(e) => {
                            e.stopPropagation();
                            onAcknowledge(alert.id);
                        }}
                        className="flex-1 flex items-center justify-center gap-2 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-600 text-xs text-slate-300 transition-colors"
                        >
                        <CheckCircle size={12} />
                        Ack
                        </button>
                    )}
                    <button 
                        onClick={() => onSelectPatient(alert.stay_id)}
                        className="flex-1 flex items-center justify-center gap-2 py-1.5 rounded bg-indigo-900/30 hover:bg-indigo-900/50 border border-indigo-800/50 text-xs text-indigo-300 transition-colors"
                    >
                        Analysis
                        <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
