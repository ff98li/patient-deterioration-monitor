import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Activity, Users, AlertOctagon, HeartPulse, Zap, WifiOff, Search, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

import { Patient, Alert, DashboardStats, RiskLevel, ConfidenceLevel } from './types';
import { fetchDashboardData, acknowledgeAlert as apiAcknowledgeAlert, checkApiHealth } from './services/apiService';
import { generateMockData } from './services/mockDataService';

import { StatCard } from './components/StatCard';
import { PatientCard } from './components/PatientCard';
import { AlertFeed } from './components/AlertFeed';
import { PatientDetailModal } from './components/PatientDetailModal';
import { RiskChart } from './components/RiskChart';

const REFRESH_INTERVAL = 2000; // 2 seconds
const PAGE_SIZE_OPTIONS = [25, 50, 100];

const App: React.FC = () => {
  // State
  const [patients, setPatients] = useState<Patient[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [useRealApi, setUseRealApi] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);

  // Filter & Pagination State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [riskFilter, setRiskFilter] = useState<RiskLevel | 'ALL'>('ALL');
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceLevel | 'ALL'>('ALL');
  const [pageSize, setPageSize] = useState<number>(25);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [showFilters, setShowFilters] = useState<boolean>(false);

  // Filtered and paginated patients
  const filteredPatients = useMemo(() => {
    return patients.filter(patient => {
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesId = patient.stay_id.toString().includes(query) || 
                          patient.subject_id.toString().includes(query);
        if (!matchesId) return false;
      }
      
      // Risk level filter
      if (riskFilter !== 'ALL' && patient.risk_level !== riskFilter) {
        return false;
      }
      
      // Confidence level filter
      if (confidenceFilter !== 'ALL' && patient.ai_confidence !== confidenceFilter) {
        return false;
      }
      
      return true;
    });
  }, [patients, searchQuery, riskFilter, confidenceFilter]);

  const totalPages = Math.ceil(filteredPatients.length / pageSize);
  
  const paginatedPatients = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredPatients.slice(startIndex, startIndex + pageSize);
  }, [filteredPatients, currentPage, pageSize]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, riskFilter, confidenceFilter, pageSize]);

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
            return [...newAlerts, ...prev].slice(0, 1000);
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
          setAlerts(prev => [mockData.newAlert!, ...prev].slice(0, 1000));
        }
      }
    } else {
      // Use mock data
      const mockData = generateMockData();
      setPatients(mockData.patients);
      setStats(mockData.stats);
      if (mockData.newAlert) {
        setAlerts(prev => [mockData.newAlert!, ...prev].slice(0, 1000));
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

  // Clear all filters
  const clearFilters = () => {
    setSearchQuery('');
    setRiskFilter('ALL');
    setConfidenceFilter('ALL');
  };

  const hasActiveFilters = searchQuery || riskFilter !== 'ALL' || confidenceFilter !== 'ALL';

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
      <div className="grid grid-cols-12 gap-6">
        
        {/* Left Col: Patient List */}
        <div className="col-span-12 lg:col-span-7 flex flex-col">
           <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-slate-100">Patient Status</h2>
              <div className="text-xs text-slate-500 bg-slate-900 px-3 py-1 rounded">
                Showing {paginatedPatients.length} of {filteredPatients.length} patients
              </div>
           </div>

           {/* Search & Filter Bar */}
           <div className="bg-slate-900 p-3 rounded-lg border border-slate-800 mb-4">
             <div className="flex flex-wrap gap-3 items-center">
               {/* Search */}
               <div className="relative flex-1 min-w-[200px]">
                 <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
                 <input
                   type="text"
                   placeholder="Search by Patient ID..."
                   value={searchQuery}
                   onChange={(e) => setSearchQuery(e.target.value)}
                   className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                 />
               </div>

               {/* Filter Toggle */}
               <button
                 onClick={() => setShowFilters(!showFilters)}
                 className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition-colors ${
                   showFilters || hasActiveFilters
                     ? 'bg-blue-900/50 border-blue-700 text-blue-300'
                     : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
                 }`}
               >
                 <Filter size={16} />
                 Filters
                 {hasActiveFilters && (
                   <span className="bg-blue-500 text-white text-xs px-1.5 rounded-full">!</span>
                 )}
               </button>

               {/* Page Size */}
               <div className="flex items-center gap-2">
                 <span className="text-xs text-slate-500">Show:</span>
                 <select
                   value={pageSize}
                   onChange={(e) => setPageSize(Number(e.target.value))}
                   className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                 >
                   {PAGE_SIZE_OPTIONS.map(size => (
                     <option key={size} value={size}>{size}</option>
                   ))}
                 </select>
               </div>
             </div>

             {/* Expanded Filters */}
             {showFilters && (
               <div className="flex flex-wrap gap-3 items-center mt-3 pt-3 border-t border-slate-800">
                 {/* Risk Level Filter */}
                 <div className="flex items-center gap-2">
                   <span className="text-xs text-slate-500">Risk:</span>
                   <select
                     value={riskFilter}
                     onChange={(e) => setRiskFilter(e.target.value as RiskLevel | 'ALL')}
                     className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                   >
                     <option value="ALL">All Levels</option>
                     <option value="CRITICAL">Critical</option>
                     <option value="HIGH">High</option>
                     <option value="MEDIUM">Medium</option>
                     <option value="LOW">Low</option>
                     <option value="NORMAL">Normal</option>
                   </select>
                 </div>

                 {/* Confidence Filter */}
                 <div className="flex items-center gap-2">
                   <span className="text-xs text-slate-500">Confidence:</span>
                   <select
                     value={confidenceFilter}
                     onChange={(e) => setConfidenceFilter(e.target.value as ConfidenceLevel | 'ALL')}
                     className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                   >
                     <option value="ALL">All Levels</option>
                     <option value="HIGH">High</option>
                     <option value="MEDIUM">Medium</option>
                     <option value="LOW">Low</option>
                   </select>
                 </div>

                 {/* Clear Filters */}
                 {hasActiveFilters && (
                   <button
                     onClick={clearFilters}
                     className="text-xs text-red-400 hover:text-red-300 ml-auto"
                   >
                     Clear All
                   </button>
                 )}
               </div>
             )}
           </div>
           
           {/* Patient List */}
           <div className="flex-1 overflow-y-auto pr-2" style={{ maxHeight: 'calc(100vh - 480px)' }}>
             {paginatedPatients.length === 0 ? (
               <div className="text-slate-500 text-center py-8">
                 {hasActiveFilters ? (
                   <>
                     No patients match your filters.
                     <br />
                     <button onClick={clearFilters} className="text-blue-400 hover:text-blue-300 text-sm mt-2">
                       Clear filters
                     </button>
                   </>
                 ) : (
                   <>
                     No patients currently being monitored.
                     <br />
                     <span className="text-sm">Start the consumer to see real-time data.</span>
                   </>
                 )}
               </div>
             ) : (
               paginatedPatients.map(patient => (
                 <PatientCard 
                   key={patient.stay_id} 
                   patient={patient} 
                   onClick={setSelectedPatient} 
                 />
               ))
             )}
           </div>

           {/* Pagination */}
           {totalPages > 1 && (
             <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-800">
               <div className="text-sm text-slate-500">
                 Page {currentPage} of {totalPages}
               </div>
               <div className="flex items-center gap-2">
                 <button
                   onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                   disabled={currentPage === 1}
                   className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                 >
                   <ChevronLeft size={16} />
                   Prev
                 </button>
                 
                 {/* Page Numbers */}
                 <div className="flex gap-1">
                   {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                     let pageNum: number;
                     if (totalPages <= 5) {
                       pageNum = i + 1;
                     } else if (currentPage <= 3) {
                       pageNum = i + 1;
                     } else if (currentPage >= totalPages - 2) {
                       pageNum = totalPages - 4 + i;
                     } else {
                       pageNum = currentPage - 2 + i;
                     }
                     return (
                       <button
                         key={pageNum}
                         onClick={() => setCurrentPage(pageNum)}
                         className={`w-8 h-8 rounded-lg text-sm ${
                           currentPage === pageNum
                             ? 'bg-blue-600 text-white'
                             : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                         }`}
                       >
                         {pageNum}
                       </button>
                     );
                   })}
                 </div>

                 <button
                   onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                   disabled={currentPage === totalPages}
                   className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                 >
                   Next
                   <ChevronRight size={16} />
                 </button>
               </div>
             </div>
           )}
        </div>

        {/* Right Col: Charts & Alerts */}
        <div className="col-span-12 lg:col-span-5 flex flex-col gap-6">
          
          {/* Risk Distribution - Compact Height */}
          <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shrink-0">
            <h3 className="text-slate-400 text-xs font-bold uppercase mb-2">Risk Distribution</h3>
            <RiskChart patients={patients} />
          </div>

          {/* Alert Feed - Takes remaining space */}
          <div className="flex-1 min-h-0" style={{ maxHeight: 'calc(100vh - 480px)' }}>
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
