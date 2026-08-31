import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  Play,
  ShieldCheck,
  Brain,
  Bot,
  User,
  CreditCard
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';
import { useAuth } from '../auth/AuthContext';

export const CaseDetail: React.FC = () => {
  const { role } = useAuth();
  const canMutate = role === 'OPS' || role === 'ADMIN';

  const { caseId } = useParams<{ caseId: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const navigate = useNavigate();

  const loadCase = async () => {
    if (!caseId) return;
    try {
      setLoading(true);
      const res = await api.getRecoveryCase(caseId);
      setData(res);
    } catch (err) {
      console.error('Failed to load case detail:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCase();
  }, [caseId]);

  const handleApprove = async () => {
    if (!caseId) return;
    try {
      setActionLoading(true);
      const res = await api.approveCase(caseId);
      if (res.run_id) {
        navigate(`/recovery/${caseId}/run/${res.run_id}`);
      }
    } catch (err) {
      console.error('Failed to approve case:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!caseId) return;
    try {
      setActionLoading(true);
      const res = await api.executeCase(caseId);
      if (res.run_id) {
        navigate(`/recovery/${caseId}/run/${res.run_id}`);
      }
    } catch (err) {
      console.error('Failed to execute case:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!caseId) return;
    try {
      setActionLoading(true);
      await api.rejectCase(caseId);
      loadCase();
    } catch (err) {
      console.error('Failed to reject case:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleEscalate = async () => {
    if (!caseId) return;
    try {
      setActionLoading(true);
      await api.escalateCase(caseId);
      loadCase();
    } catch (err) {
      console.error('Failed to escalate case:', err);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[600px]">
        <div className="text-purple-600 font-mono text-xs">Loading case context telemetry...</div>
      </div>
    );
  }

  const { payment, customer, ml_intelligence, agent_decision, guardrail_result } = data;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Top Navigation & Status Bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/recovery')}
          className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Queue
        </button>

        <div className="flex items-center gap-3">
          <StatusBadge status={data.status} />
          {data.latest_run_id && (
            <button
              onClick={() => navigate(`/recovery/${caseId}/run/${data.latest_run_id}`)}
              className="px-3 py-1.5 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 text-xs font-bold hover:bg-purple-100 transition-all cursor-pointer"
            >
              View Last Run Telemetry
            </button>
          )}
        </div>
      </div>

      {/* Case Overview Banner */}
      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white flex flex-wrap items-center justify-between gap-6">
        <div>
          <div className="text-xs text-slate-500 font-mono">Case ID: {data.id}</div>
          <h1 className="text-2xl font-black text-slate-900 mt-1">
            ${payment?.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })} Revenue At Risk
          </h1>
          <p className="text-xs text-slate-500 mt-1">Customer: <strong className="text-slate-900">{customer?.name}</strong> • Failure Reason: <span className="text-rose-600 font-bold">{payment?.failure_reason}</span></p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          {canMutate ? (
            <>
              <button
                onClick={handleReject}
                disabled={actionLoading || data.status === 'RECOVERED' || data.status === 'STOPPED'}
                className="px-4 py-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold hover:bg-rose-100 disabled:opacity-40 cursor-pointer"
              >
                Reject
              </button>
              <button
                onClick={handleEscalate}
                disabled={actionLoading || data.status === 'RECOVERED'}
                className="px-4 py-2 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 text-xs font-bold hover:bg-purple-100 disabled:opacity-40 cursor-pointer"
              >
                Escalate
              </button>
              <button
                onClick={handleApprove}
                disabled={actionLoading || data.status === 'RECOVERED' || data.status === 'STOPPED'}
                className="btn-primary flex items-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                Approve Action
              </button>
              <button
                onClick={handleExecute}
                disabled={actionLoading || data.status === 'RECOVERED' || data.status === 'STOPPED'}
                className="btn-dark flex items-center gap-2"
              >
                <Play className="w-4 h-4 fill-current" />
                Execute Live Run
              </button>
            </>
          ) : (
            <div className="text-xs text-slate-400 font-bold px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 cursor-not-allowed">
              Action Execution Restricted (OPS / ADMIN Required)
            </div>
          )}
        </div>
      </div>

      {/* Grid Layout: Context vs Decisions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Contexts */}
        <div className="space-y-6">
          {/* Payment Information */}
          <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-purple-600" />
              Payment Details
            </h2>
            <div className="space-y-2 text-xs divide-y divide-slate-100">
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Gateway ID</span><span className="font-mono text-slate-900 font-medium">{payment?.gateway_payment_id}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Amount</span><span className="font-mono font-bold text-slate-900">${payment?.amount?.toLocaleString()}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Status</span><StatusBadge status={payment?.status} /></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Failure Reason</span><span className="font-mono text-rose-600 font-bold">{payment?.failure_reason}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Attempt Count</span><span className="font-mono text-slate-900">{data.retry_count} / 3</span></div>
            </div>
          </div>

          {/* Customer Context */}
          <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <User className="w-4 h-4 text-purple-600" />
              Customer Profile 360
            </h2>
            <div className="space-y-2 text-xs divide-y divide-slate-100">
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Name</span><span className="font-bold text-slate-900">{customer?.name}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Email</span><span className="font-mono text-slate-700">{customer?.email}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Lifetime Value</span><span className="font-mono font-bold text-emerald-600">${customer?.lifetime_value?.toLocaleString()}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Successful Payments</span><span className="font-mono text-slate-900">{customer?.successful_payments}</span></div>
              <div className="flex justify-between py-1.5"><span className="text-slate-500">Opted Out</span><StatusBadge status={customer?.opted_out ? 'TRUE' : 'FALSE'} type="boolean" /></div>
            </div>
          </div>
        </div>

        {/* Middle Column: ML & Agent Intelligence */}
        <div className="space-y-6">
          {/* ML Intelligence Card */}
          <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Brain className="w-4 h-4 text-emerald-600" />
              ML Recovery Intelligence
            </h2>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <div className="text-[10px] text-slate-500 uppercase font-mono">Root Cause Diagnosis</div>
                <div className="text-xs font-bold text-purple-700 mt-1">{ml_intelligence?.root_cause}</div>
                <div className="text-[10px] text-slate-400 mt-1">Rule-Based Rules Evaluated</div>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <div className="text-[10px] text-slate-500 uppercase font-mono">P(Recovery)</div>
                <div className="text-xs font-bold text-emerald-600 mt-1">{((ml_intelligence?.recovery_probability || 0.5) * 100).toFixed(0)}%</div>
                <div className="text-[10px] text-slate-400 mt-1">ML Recovery Prediction</div>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex justify-between items-center text-xs">
              <span className="text-slate-600 font-medium">Expected Recoverable Revenue</span>
              <span className="font-mono font-black text-purple-700 text-sm">${ml_intelligence?.expected_recovery?.toLocaleString()}</span>
            </div>
          </div>

          {/* Recovery Agent Decision */}
          <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Bot className="w-4 h-4 text-purple-600" />
              Recovery Agent Recommendation
            </h2>

            <div className="p-4 rounded-xl bg-purple-50 border border-purple-200 space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-bold text-purple-900 text-xs">Proposed Action:</span>
                <StatusBadge status={agent_decision?.recommended_action || 'RETRY'} type="action" />
              </div>
              <p className="text-slate-700 text-xs">{agent_decision?.reason}</p>
            </div>
          </div>
        </div>

        {/* Right Column: Guardrails & Timeline */}
        <div className="space-y-6">
          {/* Guardrails Validation Card */}
          <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-purple-600" />
              Policy Guardrails Validation
            </h2>

            <div className={`p-4 rounded-xl border ${guardrail_result?.allowed ? 'bg-[#F0FDF4] border-emerald-200 text-[#16A34A]' : 'bg-[#FEF2F2] border-rose-200 text-[#DC2626]'}`}>
              <div className="font-bold text-xs">
                {guardrail_result?.allowed ? 'ACTION ALLOWED BY GUARDRAILS' : 'ACTION BLOCKED BY POLICY'}
              </div>
              <p className="text-[11px] mt-1 text-slate-700">{guardrail_result?.reason}</p>
            </div>

            <div className="space-y-2 text-xs">
              {guardrail_result?.checks && Object.entries(guardrail_result.checks).map(([k, v]: [string, any]) => (
                <div key={k} className="flex justify-between items-center border-b border-slate-100 pb-1.5">
                  <span className="text-slate-600 capitalize">{k.replace('_', ' ')}:</span>
                  <StatusBadge status={v.passed ? 'PASSED' : 'BLOCKED'} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
