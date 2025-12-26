import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Users, AlertOctagon, HeartPulse, Zap, WifiOff } from 'lucide-react';

import { Patient, Alert, DashboardStats } from './types';
import { fetchDashboardData, acknowledgeAlert as apiAcknowledgeAlert, checkApiHealth } from './services/apiService';
import { generateMockData } from './services/mockDataService';

import { StatCard } from './components/StatCard';
import { PatientCard } from './components/PatientCard';
import { AlertFeed } from './components/AlertFeed';
import { PatientDetailModal } from './components/PatientDetailModal';
import { RiskChart } from './components/RiskChart';

const REFRESH_INTERVAL = 2000; // 2 seconds

const App: React.FC = () => {
  // State
  const [patients, setPatients] = useState<Patient[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [useRealApi, setUseRealApi] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);

  // Fetch data from API or fall back to mock
  const fetchData = useCallback(async () => {
    if (useRealApi) {
      try {
        const data = await fetchDashboardData();
        setPatients(data.patients);
        setStats(data.stats);
        
        // Merge new alerts (avoid duplicates)
        if (data.alerts && data.alerts.length > 0) {
          setAlerts(prev => {
            const existingIds = new Set(prev.map(a => a.id));
            const newAlerts = data.alerts.filter(a => !existingIds.has(a.id));
            return [...newAlerts, ...prev].slice(0, 50);
          });
        }
        
        setApiError(null);
      } catch (error) {
        console.error('API fetch failed:', error);
        setApiError('Failed to connect to backend. Using demo mode.');
        // Fall back to mock data
        const mockData = generateMockData();
        setPatients(mockData.patients);
        setStats(mockData.stats);
        if (mockData.newAlert) {
          setAlerts(prev => [mockData.newAlert!, ...prev].slice(0, 50));
        }
      }
    } else {
      // Use mock data
      const mockData = generateMockData();
      setPatients(mockData.patients);
      setStats(mockData.stats);
      if (mockData.newAlert) {
        setAlerts(prev => [mockData.newAlert!, ...prev].slice(0, 50));
      }
    }
    setCurrentTime(new Date());
  }, [useRealApi]);

  // Initial load and health check
  useEffect(() => {
    const init = async () => {
      const apiAvailable = await checkApiHealth();
      setUseRealApi(apiAvailable);
      if (!apiAvailable) {
        setApiError('Backend not available. Running in demo mode with simulated data.');
      }
      fetchData();
    };
    init();
  }, []);

  // Refresh loop
  useEffect(() => {
    const interval = setInterval(fetchData, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Handle alert acknowledgment
  const handleAcknowledgeAlert = async (id: string) => {
    if (useRealApi) {
      const success = await apiAcknowledgeAlert(id);
      if (success) {
        setAlerts(prev => prev.map(a => 
          a.id === id ? { ...a, is_acknowledged: true } : a
        ));
      }
    } else {
      // Mock mode - just update local state
      setAlerts(prev => prev.map(a => 
        a.id === id ? { ...a, is_acknowledged: true } : a
      ));
    }
  };

  const handleSelectPatientFromAlert = (stayId: number) => {
    const patient = patients.find(p => p.stay_id === stayId);
    if (patient) {
      setSelectedPatient(patient);
    }
  };

  // Toggle between real API and mock data (for testing)
  const toggleDataSource = () => {
    setUseRealApi(prev => !prev);
    setApiError(null);
  };

  if (!stats) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-500">
        <div className="text-center">
          <HeartPulse className="animate-pulse mx-auto mb-4" size={48} />
          <p>Initializing Monitor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6 pb-20">
      
      {/* API Error Banner */}
      {apiError && (
        <div className="bg-amber-900/50 border border-amber-700 text-amber-200 px-4 py-2 rounded-lg mb-4 flex items-center gap-2 text-sm">
          <WifiOff size={16} />
          {apiError}
          <button 
            onClick={toggleDataSource}
            className="ml-auto text-xs bg-amber-800 hover:bg-amber-700 px-2 py-1 rounded"
          >
            {useRealApi ? 'Switch to Demo' : 'Try Real API'}
          </button>
        </div>
      )}

      {/* Header */}
      <header className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
            <HeartPulse className="text-rose-500" size={32} />
            Patient Deterioration Monitor
          </h1>
          <p className="text-slate-400 mt-1 flex items-center gap-2 text-sm">
            Powered by Confluent Kafka & Vertex AI
            <span className="w-1 h-1 bg-slate-600 rounded-full"></span>
            ICU Ward 3
            {!useRealApi && (
              <>
                <span className="w-1 h-1 bg-slate-600 rounded-full"></span>
                <span className="text-amber-400">Demo Mode</span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-4">
           <div className="flex items-center gap-2 bg-slate-900 px-4 py-2 rounded-full border border-slate-800">
             <div className="relative flex h-3 w-3">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${useRealApi ? 'bg-emerald-400' : 'bg-amber-400'} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-3 w-3 ${useRealApi ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
              </div>
              <span className={`${useRealApi ? 'text-emerald-400' : 'text-amber-400'} text-sm font-medium`}>
                {useRealApi ? 'System Live' : 'Demo Mode'}
              </span>
              <span className="text-slate-600 text-xs border-l border-slate-700 pl-2 ml-1 font-mono">
                {currentTime.toLocaleTimeString()}
              </span>
           </div>
        </div>
      </header>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard 
          title="Patients Monitored" 
          value={stats.total_patients} 
          icon={Users} 
          colorClass="text-blue-400" 
        />
        <StatCard 
          title="Critical Risk" 
          value={stats.critical_count} 
          icon={AlertOctagon} 
          colorClass="text-red-500"
          subtext="Immediate Attention Required"
        />
        <StatCard 
          title="High Risk" 
          value={stats.high_count} 
          icon={Activity} 
          colorClass="text-orange-400" 
        />
        <StatCard 
          title="Alerts (24h)" 
          value={stats.alerts_today} 
          icon={Zap} 
          colorClass="text-yellow-400"
          subtext={`${alerts.filter(a => !a.is_acknowledged).length} Unacknowledged`}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6 h-[calc(100vh-280px)]">
        
        {/* Left Col: Patient List */}
        <div className="col-span-12 lg:col-span-7 flex flex-col h-full">
           <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-slate-100">Patient Status</h2>
              <div className="text-xs text-slate-500 bg-slate-900 px-3 py-1 rounded">Sorted by Risk Severity</div>
           </div>
           
           <div className="flex-1 overflow-y-auto pr-2">
             {patients.length === 0 ? (
               <div className="text-slate-500 text-center py-8">
                 No patients currently being monitored.
                 <br />
                 <span className="text-sm">Start the consumer to see real-time data.</span>
               </div>
             ) : (
               patients.map(patient => (
                 <PatientCard 
                   key={patient.stay_id} 
                   patient={patient} 
                   onClick={setSelectedPatient} 
                 />
               ))
             )}
           </div>
        </div>

        {/* Right Col: Charts & Alerts */}
        <div className="col-span-12 lg:col-span-5 flex flex-col h-full gap-6">
          
          {/* Risk Distribution - Compact Height */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shrink-0">
            <h3 className="text-slate-400 text-xs font-bold uppercase mb-2">Risk Distribution</h3>
            <RiskChart patients={patients} />
          </div>

          {/* Alert Feed - Takes remaining space */}
          <div className="flex-1 min-h-0">
            <AlertFeed 
              alerts={alerts} 
              onAcknowledge={handleAcknowledgeAlert} 
              onSelectPatient={handleSelectPatientFromAlert}
            />
          </div>

        </div>
      </div>

      {/* Drilldown Modal */}
      {selectedPatient && (
        <PatientDetailModal 
          patient={selectedPatient} 
          onClose={() => setSelectedPatient(null)} 
        />
      )}

    </div>
  );
};

export default App;
