import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, Filter } from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const RecoveryQueue: React.FC = () => {
  const [cases, setCases] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('ACTIVE');
  const [actionFilter, setActionFilter] = useState('');
  const [rootCauseFilter, setRootCauseFilter] = useState('');

  const navigate = useNavigate();

  const fetchCases = async () => {
    try {
      setLoading(true);
      const params: Record<string, any> = {};
      if (activeFilter) {
        params.status = activeFilter;
      }
      if (actionFilter) params.recommended_action = actionFilter;
      if (rootCauseFilter) params.root_cause = rootCauseFilter;

      const res = await api.getRecoveryCases(params);
      setCases(res.cases || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to fetch recovery cases:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [activeFilter, actionFilter, rootCauseFilter]);

  const filterTabs = [
    { id: 'ACTIVE', label: 'All Active' },
    { id: 'PRIORITIZED', label: 'Prioritized' },
    { id: 'CUSTOMER_ACTION_REQUIRED', label: 'Customer Action' },
    { id: 'NEEDS_REVIEW', label: 'Human Review' },
    { id: 'STOPPED', label: 'Stopped' },
    { id: 'RECOVERED', label: 'Recovered' },
    { id: 'ALL', label: 'All' },
  ];

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            Recovery Queue
            <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
              {total} {activeFilter === 'RECOVERED' ? 'Recovered Cases' : 'Cases Ranked'}
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {activeFilter === 'RECOVERED'
              ? 'Successfully recovered payment cases.'
              : activeFilter === 'STOPPED'
              ? 'Halted / exhausted recovery cases.'
              : 'Unresolved operational cases automatically prioritized by Expected Recoverable Revenue (Amount × P(Recovery)).'}
          </p>
        </div>
        <button
          onClick={fetchCases}
          className="btn-dark flex items-center gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Queue
        </button>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 glass-panel rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveFilter(tab.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeFilter === tab.id
                  ? 'bg-[#1E1E24] text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>


        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer"
            >
              <option value="">All Actions</option>
              <option value="RETRY">RETRY</option>
              <option value="CUSTOMER_NUDGE">CUSTOMER_NUDGE</option>
              <option value="HUMAN_REVIEW">HUMAN_REVIEW</option>
              <option value="STOP">STOP</option>
            </select>
          </div>

          <select
            value={rootCauseFilter}
            onChange={(e) => setRootCauseFilter(e.target.value)}
            className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer"
          >
            <option value="">All Failure Reasons</option>
            <option value="TRANSIENT_FAILURE">TRANSIENT_FAILURE</option>
            <option value="CUSTOMER_ACTION">CUSTOMER_ACTION</option>
            <option value="RISK_RELATED">RISK_RELATED</option>
            <option value="OTHER">OTHER</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      <div className="glass-panel rounded-xl border border-slate-200 bg-white overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-xs font-mono">Loading cases...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-3.5 pl-4">Priority</th>
                  <th className="py-3.5">Case ID</th>
                  <th className="py-3.5">Customer</th>
                  <th className="py-3.5">Amount</th>
                  <th className="py-3.5">Failure Reason</th>
                  <th className="py-3.5">P(Recovery)</th>
                  <th className="py-3.5">Expected Recovery</th>
                  <th className="py-3.5">Recommended Action</th>
                  <th className="py-3.5 pr-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cases.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/recovery/${c.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 pl-4 font-mono font-bold text-purple-600">#{c.priority}</td>
                    <td className="py-3.5 font-mono text-slate-500 text-[11px]">{c.id.substring(0, 8)}...</td>
                    <td className="py-3.5 font-bold text-slate-900">{c.customer_name}</td>
                    <td className="py-3.5 font-mono font-bold text-slate-900">${c.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                    <td className="py-3.5 font-mono text-slate-600">{c.failure_reason}</td>
                    <td className="py-3.5 font-mono font-bold text-emerald-600">{(c.recovery_probability * 100).toFixed(0)}%</td>
                    <td className="py-3.5 font-mono font-bold text-purple-600">${c.expected_recovery?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                    <td className="py-3.5">
                      <StatusBadge status={c.recommended_action || 'RETRY'} type="action" />
                    </td>
                    <td className="py-3.5 pr-4">
                      <StatusBadge status={c.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
