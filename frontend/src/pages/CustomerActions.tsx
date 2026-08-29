import React, { useEffect, useState } from 'react';
import {
  UserCheck,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Zap,
  ArrowRight,
  ShieldAlert,
  Send,
  Bell,
  Mail
} from 'lucide-react';
import { api } from '../api/client';
import { MetricCard } from '../components/common/MetricCard';
import { StatusBadge } from '../components/common/StatusBadge';

export const CustomerActions: React.FC = () => {
  const [cases, setCases] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const [resCases, resSummary] = await Promise.all([
        api.getRecoveryCases({ status: 'CUSTOMER_ACTION_REQUIRED', limit: 100 }),
        api.getDashboardSummary()
      ]);
      setCases(resCases.cases || []);
      setSummary(resSummary);
      
      if (!selectedCaseId && resCases.cases && resCases.cases.length > 0) {
        setSelectedCaseId(resCases.cases[0].id);
      }
    } catch (err) {
      console.error('Failed to load customer action cases:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!selectedCaseId) return;
    async function loadDetail() {
      try {
        setDetailLoading(true);
        const data = await api.getRecoveryCase(selectedCaseId!);
        setDetail(data);
      } catch (err) {
        console.error('Failed to load case detail:', err);
      } finally {
        setDetailLoading(false);
      }
    }
    loadDetail();
  }, [selectedCaseId]);

  const handleSimulateCustomerAction = async () => {
    if (!selectedCaseId) return;
    try {
      setActionLoading(true);
      await api.completeCustomerAction(selectedCaseId);
      await loadData();
      const updated = await api.getRecoveryCase(selectedCaseId);
      setDetail(updated);
    } catch (err) {
      console.error('Failed to simulate customer action:', err);
      alert('Failed to simulate customer action. Check console logs.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReevaluateNow = async () => {
    if (!selectedCaseId) return;
    try {
      setActionLoading(true);
      await api.reevaluateCase(selectedCaseId);
      await loadData();
      const updated = await api.getRecoveryCase(selectedCaseId);
      setDetail(updated);
    } catch (err) {
      console.error('Failed to re-evaluate case:', err);
      alert('Failed to re-evaluate case.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[600px]">
        <div className="flex items-center gap-3 text-purple-600 font-semibold font-mono text-sm">
          <Zap className="w-5 h-5 animate-spin" />
          Loading Customer Action Queue...
        </div>
      </div>
    );
  }

  const actionInfo = detail?.customer_action_info || {};
  const isOptedOut = detail?.customer?.opted_out;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            Customer Actions Operations
            <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 font-mono border border-blue-200 font-bold">
              External Action Required
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Cases waiting for customer intervention (e.g. Add Funds, Update Card, 3DS Auth)
          </p>
        </div>
        <button
          onClick={loadData}
          className="btn-outline text-xs flex items-center gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Stream
        </button>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Pending Customer Actions"
          value={summary?.customer_actions_pending || 0}
          subtitle="Waiting for Customer Fix"
          icon={<Clock className="w-4 h-4 text-amber-500" />}
          color="amber"
        />
        <MetricCard
          title="Completed Customer Actions"
          value={summary?.customer_actions_completed || 0}
          subtitle="Fixed & Re-evaluated"
          icon={<CheckCircle2 className="w-4 h-4 text-emerald-500" />}
          color="emerald"
        />
        <MetricCard
          title="Expired Windows"
          value={summary?.customer_actions_expired || 0}
          subtitle="Window Elapsed -> Stopped"
          icon={<XCircle className="w-4 h-4 text-rose-500" />}
          color="rose"
        />
        <MetricCard
          title="Recovered via Customer Fix"
          value={summary?.customer_actions_recovered || 0}
          subtitle="Successfully Captured"
          icon={<UserCheck className="w-4 h-4 text-purple-600" />}
          color="purple"
        />
      </div>

      {/* Main Grid: Queue Table + Detail Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Table View */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-blue-600" />
            Customer Action Queue ({cases.length})
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-2.5 pl-3">Customer</th>
                  <th className="py-2.5">Amount</th>
                  <th className="py-2.5">Failure Reason</th>
                  <th className="py-2.5">Required Action</th>
                  <th className="py-2.5">Action Status</th>
                  <th className="py-2.5 pr-3">Case Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400 text-xs font-mono">
                      No pending customer action cases found.
                    </td>
                  </tr>
                ) : (
                  cases.map((item) => (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedCaseId(item.id)}
                      className={`cursor-pointer transition-colors ${
                        selectedCaseId === item.id ? 'bg-purple-50/70 border-l-4 border-purple-600' : 'hover:bg-slate-50'
                      }`}
                    >
                      <td className="py-3 pl-3 font-bold text-slate-900">{item.customer_name}</td>
                      <td className="py-3 font-mono font-bold text-slate-900">${item.amount?.toLocaleString()}</td>
                      <td className="py-3 text-slate-700">{item.failure_reason}</td>
                      <td className="py-3 font-mono text-purple-700 font-semibold">{item.customer_action_type || 'ADD_FUNDS'}</td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
                          item.customer_action_status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                          item.customer_action_status === 'EXPIRED' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                          'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}>
                          {item.customer_action_status || 'PENDING'}
                        </span>
                      </td>
                      <td className="py-3 pr-3">
                        <StatusBadge status={item.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Case Detail Panel */}
        <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-6">
          {detailLoading ? (
            <div className="py-12 flex items-center justify-center text-xs font-mono text-slate-400 gap-2">
              <RefreshCw className="w-4 h-4 animate-spin" /> Loading detail...
            </div>
          ) : !detail ? (
            <div className="py-12 text-center text-xs text-slate-400">Select a case to inspect detail</div>
          ) : (
            <>
              {/* Header Info */}
              <div className="space-y-2 border-b border-slate-100 pb-4">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase text-slate-400 font-bold">Case ID</span>
                  <StatusBadge status={detail.status} />
                </div>
                <h3 className="text-base font-black text-slate-900">{detail.customer?.name}</h3>
                <p className="text-xs text-slate-500 font-mono">{detail.customer?.email}</p>
              </div>

              {/* Payment Details */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
                <div className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                  Payment Failure Context
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div><span className="text-slate-400">Amount:</span> <span className="font-mono font-bold">${detail.payment?.amount}</span></div>
                  <div><span className="text-slate-400">Reason:</span> <span className="font-semibold text-rose-600">{detail.payment?.failure_reason}</span></div>
                  <div><span className="text-slate-400">Attempt:</span> <span className="font-mono">#{detail.payment?.attempt_number}</span></div>
                  <div><span className="text-slate-400">Root Cause:</span> <span className="font-mono">{detail.ml_intelligence?.root_cause}</span></div>
                </div>
              </div>

              {/* Required Customer Action */}
              <div className="p-4 bg-purple-50/60 rounded-xl border border-purple-200 space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-purple-900">
                  <span className="flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-purple-600" />
                    Required Customer Action
                  </span>
                  <span className="font-mono px-2 py-0.5 rounded bg-purple-100 text-purple-800 text-[10px]">
                    {actionInfo.type || 'ADD_FUNDS'}
                  </span>
                </div>
                <p className="text-xs text-purple-950 font-medium">
                  {actionInfo.description || 'Customer must add sufficient funds to their billing account.'}
                </p>
              </div>

              {/* Notification Status */}
              <div className="p-3 rounded-xl border border-slate-200 space-y-1.5 text-xs bg-white">
                <div className="font-bold text-slate-800 flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-blue-500" />
                  Customer Notification
                </div>
                {isOptedOut ? (
                  <div className="p-2 rounded bg-rose-50 text-rose-800 text-[11px] border border-rose-200 flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
                    <div>
                      <span className="font-bold">Notification Blocked</span>
                      <p className="text-[10px] text-rose-600">Reason: Customer opted out of automatic recovery communications</p>
                    </div>
                  </div>
                ) : (
                  <div className="p-2 rounded bg-emerald-50 text-emerald-800 text-[11px] border border-emerald-200 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <div>
                      <span className="font-bold">Notification Dispatched</span>
                      <p className="text-[10px] text-emerald-600">Customer notified to take action.</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Lifecycle Timeline */}
              <div className="space-y-2 text-xs">
                <span className="font-bold text-slate-800 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-amber-500" />
                  Waiting Lifecycle Windows
                </span>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 font-mono text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Waiting Since:</span>
                    <span className="font-bold text-slate-800">{actionInfo.waiting_since ? new Date(actionInfo.waiting_since).toLocaleString() : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Next Re-evaluation:</span>
                    <span className="font-bold text-purple-700">{actionInfo.retry_after ? new Date(actionInfo.retry_after).toLocaleString() : '24h window'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Window Expires:</span>
                    <span className="font-bold text-rose-600">{actionInfo.expires_at ? new Date(actionInfo.expires_at).toLocaleString() : '72h limit'}</span>
                  </div>
                </div>
              </div>

              {/* Test Mode Interactive Actions */}
              <div className="pt-2 border-t border-slate-100 space-y-2">
                <span className="text-[10px] font-mono text-slate-400 font-bold uppercase block">Test Mode Simulation Controls</span>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={handleSimulateCustomerAction}
                    disabled={actionLoading || detail.status === 'RECOVERED'}
                    className="btn-primary text-xs flex items-center justify-center gap-1.5 py-2.5 disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Simulate Fix
                  </button>
                  <button
                    onClick={handleReevaluateNow}
                    disabled={actionLoading || detail.status === 'RECOVERED'}
                    className="btn-outline text-xs flex items-center justify-center gap-1.5 py-2.5 text-purple-700 border-purple-200 hover:bg-purple-50 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                    Re-evaluate
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
