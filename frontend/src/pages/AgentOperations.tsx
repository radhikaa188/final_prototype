import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, Activity, CheckCircle2, ShieldAlert, AlertTriangle } from 'lucide-react';
import { api } from '../api/client';
import { MetricCard } from '../components/common/MetricCard';
import { StatusBadge } from '../components/common/StatusBadge';

export const AgentOperations: React.FC = () => {
  const [runs, setRuns] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();

  useEffect(() => {
    async function loadAgentOps() {
      try {
        setLoading(true);
        const res = await api.getAgentRuns();
        setRuns(res.runs || []);
        setTotal(res.total || 0);
      } catch (err) {
        console.error('Failed to load agent runs:', err);
      } finally {
        setLoading(false);
      }
    }
    loadAgentOps();
  }, []);

  const completedCount = runs.filter((r) => r.status === 'COMPLETED' || r.final_result === 'RECOVERED').length;
  const blockedCount = runs.filter((r) => r.status === 'BLOCKED').length;
  const escalatedCount = runs.filter((r) => r.status === 'ESCALATED' || r.final_result === 'ESCALATED').length;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Agent Operations &amp; Monitoring
          <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
            {total} Workflow Runs
          </span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">Autonomous decision history, agent execution telemetry, and operational performance metrics</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard title="Total Agent Runs" value={total} subtitle="Workflow executions" icon={<Bot className="w-4 h-4 text-purple-600" />} color="cyan" />
        <MetricCard title="Successful Recoveries" value={completedCount} subtitle="Resolution achieved" icon={<CheckCircle2 className="w-4 h-4 text-emerald-600" />} color="emerald" />
        <MetricCard title="Escalations" value={escalatedCount} subtitle="Routed to Human Ops" icon={<ShieldAlert className="w-4 h-4 text-purple-600" />} color="purple" />
        <MetricCard title="Policy Blocked" value={blockedCount} subtitle="Stopped by Guardrails" icon={<AlertTriangle className="w-4 h-4 text-rose-500" />} color="rose" />
      </div>

      {/* Recent Agent Runs Table */}
      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
        <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <Activity className="w-4 h-4 text-purple-600" />
          Recent Agent Executions
        </h2>

        {loading ? (
          <div className="p-8 text-center text-slate-500 text-xs font-mono">Loading agent runs...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-3 pl-3">Run ID</th>
                  <th className="py-3">Case ID</th>
                  <th className="py-3">Amount</th>
                  <th className="py-3">Recommended Action</th>
                  <th className="py-3">Trigger Type</th>
                  <th className="py-3">Status</th>
                  <th className="py-3 pr-3">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {runs.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => navigate(`/recovery/${r.case_id}/run/${r.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 pl-3 font-mono text-purple-700 font-bold">{r.id.substring(0, 8)}...</td>
                    <td className="py-3 font-mono text-slate-500">{r.case_id.substring(0, 8)}...</td>
                    <td className="py-3 font-mono font-bold text-slate-900">${r.amount?.toLocaleString()}</td>
                    <td className="py-3"><StatusBadge status={r.recommended_action || 'RETRY'} type="action" /></td>
                    <td className="py-3 font-mono text-slate-500 text-[10px]">{r.trigger_type}</td>
                    <td className="py-3"><StatusBadge status={r.status} /></td>
                    <td className="py-3 pr-3 font-mono text-slate-500">{r.started_at ? new Date(r.started_at).toLocaleString() : 'N/A'}</td>
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
