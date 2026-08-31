import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  Zap,
  Activity,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { api } from '../api/client';
import { MetricCard } from '../components/common/MetricCard';
import { StatusBadge } from '../components/common/StatusBadge';

export const CommandCenter: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [revenueTimeline, setRevenueTimeline] = useState<any[]>([]);
  const [funnel, setFunnel] = useState<any[]>([]);
  const [priorityCases, setPriorityCases] = useState<any[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [sumRes, revRes, funnelRes, casesRes, actRes] = await Promise.all([
          api.getDashboardSummary(),
          api.getDashboardRevenue(),
          api.getDashboardFunnel(),
          api.getRecoveryCases({ limit: 5 }),
          api.getDashboardActivity(),
        ]);
        setSummary(sumRes);
        setRevenueTimeline(revRes);
        setFunnel(funnelRes);
        setPriorityCases(casesRes.cases || []);
        setActivities(actRes || []);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[600px]">
        <div className="flex items-center gap-3 text-purple-600 font-semibold font-mono text-sm">
          <Zap className="w-5 h-5 animate-spin" />
          Loading Command Center Telemetry...
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Page Title Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            Command Center
            <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
              Live Operations
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">Autonomous Revenue Recovery Orchestration & Real-Time Monitoring</p>
        </div>
        <button
          onClick={() => navigate('/recovery')}
          className="btn-dark flex items-center gap-2"
        >
          View Full Recovery Queue
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* 5 Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <MetricCard
          title="Revenue At Risk"
          value={`$${(summary?.revenue_at_risk || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          subtitle="Failed Subscription Charges"
          icon={<AlertTriangle className="w-4 h-4 text-rose-500" />}
          color="rose"
        />
        <MetricCard
          title="Recoverable Revenue"
          value={`$${(summary?.recoverable_revenue || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          subtitle="P(Recovery) Weighted"
          icon={<TrendingUp className="w-4 h-4 text-amber-500" />}
          color="amber"
        />
        <MetricCard
          title="Revenue Recovered"
          value={`$${(summary?.revenue_recovered || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          subtitle="Successfully Captured"
          icon={<DollarSign className="w-4 h-4 text-emerald-500" />}
          color="emerald"
        />
        <MetricCard
          title="Recovery Rate"
          value={`${((summary?.recovery_rate || 0) * 100).toFixed(1)}%`}
          subtitle="Overall Efficiency"
          icon={<Zap className="w-4 h-4 text-purple-600" />}
          color="purple"
        />
        <MetricCard
          title="Active Cases"
          value={summary?.active_cases || 0}
          subtitle={`Out of ${summary?.total_cases || 0} total`}
          icon={<Activity className="w-4 h-4 text-blue-500" />}
          color="cyan"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Timeline Chart */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Activity className="w-4 h-4 text-purple-600" />
                Revenue Recovery Timeline
              </h2>
              <p className="text-xs text-slate-500">Comparing Revenue At Risk vs Recoverable Revenue vs Recovered over time</p>
            </div>
          </div>
          <div className="h-72 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={revenueTimeline}>
                <defs>
                  <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorRecoverable" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} tickFormatter={(val) => `$${val}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E5E7EB', borderRadius: '8px', fontSize: '12px', color: '#111827' }}
                  formatter={(val: any) => [`$${Number(val).toLocaleString()}`, '']}
                />
                <Area type="monotone" dataKey="at_risk" name="Revenue at Risk" stroke="#ef4444" fillOpacity={1} fill="url(#colorRisk)" />
                <Area type="monotone" dataKey="recoverable" name="Recoverable Revenue" stroke="#f59e0b" fillOpacity={1} fill="url(#colorRecoverable)" />
                <Area type="monotone" dataKey="recovered" name="Recovered Revenue" stroke="#10b981" fillOpacity={1} fill="url(#colorRecovered)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recovery Funnel */}
        <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-600" />
              Recovery Conversion Funnel
            </h2>
            <p className="text-xs text-slate-500">Cumulative progression of failed payments through resolution</p>
          </div>

          <div className="space-y-3 pt-2">
            {funnel.map((item, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-700 font-medium">{item.stage}</span>
                  <span className="font-mono text-slate-900 font-bold">{item.count}</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, Math.max(8, (item.count / (funnel[0]?.count || 1)) * 100))}%`,
                      backgroundColor: item.color
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Priority Cases & Recent Agent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Priority Cases */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-purple-600" />
              Highest Priority Recovery Cases
            </h2>
            <button
              onClick={() => navigate('/recovery')}
              className="text-xs text-purple-600 font-bold hover:underline cursor-pointer"
            >
              View All Queue
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-2.5 pl-3">Priority</th>
                  <th className="py-2.5">Customer</th>
                  <th className="py-2.5">Amount</th>
                  <th className="py-2.5">P(Recovery)</th>
                  <th className="py-2.5">Expected Recovery</th>
                  <th className="py-2.5">Action</th>
                  <th className="py-2.5 pr-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {priorityCases.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => navigate(`/recovery/${item.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 pl-3 font-mono font-bold text-purple-600">#{item.priority}</td>
                    <td className="py-3 font-bold text-slate-900">{item.customer_name}</td>
                    <td className="py-3 font-mono font-bold text-slate-900">${item.amount?.toLocaleString()}</td>
                    <td className="py-3 font-mono text-emerald-600 font-bold">{(item.recovery_probability * 100).toFixed(0)}%</td>
                    <td className="py-3 font-mono font-bold text-purple-600">${item.expected_recovery?.toLocaleString()}</td>
                    <td className="py-3">
                      <StatusBadge status={item.recommended_action || 'RETRY'} type="action" />
                    </td>
                    <td className="py-3 pr-3">
                      <StatusBadge status={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live Agent Activity */}
        <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-600" />
            Live Agent Audit Stream
          </h2>

          <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
            {activities.map((act) => (
              <div key={act.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                <div className="flex items-center justify-between text-[10px] text-slate-500">
                  <span className="font-mono text-purple-700 font-bold">{act.actor_type}</span>
                  <span>{new Date(act.timestamp).toLocaleTimeString()}</span>
                </div>
                <p className="text-slate-800 text-xs font-medium">{act.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
