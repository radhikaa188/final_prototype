import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
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

  const [currentTime, setCurrentTime] = useState(Date.now());
  const [scheduleNotice, setScheduleNotice] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

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


  const { payment, customer, ml_intelligence, agent_decision, guardrail_result, customer_action_info } = data;
  const isRecovered = data.status === 'RECOVERED';
  const isStopped = data.status === 'STOPPED';
  const isCustomerAction = data.status === 'CUSTOMER_ACTION_REQUIRED';
  const isEscalated = data.status === 'ESCALATED';
  const isReevaluating = data.status === 'RE_EVALUATING';

  const retryAfterTime = data.retry_after ? new Date(data.retry_after).getTime() : null;
  const isFutureRetry = retryAfterTime ? retryAfterTime > currentTime : false;
  const remainingSeconds = retryAfterTime ? Math.max(0, Math.floor((retryAfterTime - currentTime) / 1000)) : 0;
  const formatCountdown = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const handleSimulateCustomerAction = async () => {
    if (!caseId) return;
    try {
      setActionLoading(true);
      await api.completeCustomerAction(caseId);
      loadCase();
    } catch (err) {
      console.error('Failed to simulate customer action:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReevaluate = async () => {
    if (!caseId) return;
    try {
      setActionLoading(true);
      const res = await api.reevaluateCase(caseId);
      if (res.status === 'SCHEDULED') {
        setScheduleNotice(`Retry schedule confirmed for ${new Date(res.retry_after).toLocaleTimeString()}. The autonomous backend scheduler will execute automatically when the retry window opens.`);
      } else {
        setScheduleNotice(null);
      }
      loadCase();
    } catch (err: any) {
      console.error('Failed to re-evaluate case:', err);
      alert(`Re-evaluation blocked: ${err.message || err}`);
    } finally {
      setActionLoading(false);
    }
  };

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

      {/* Recovered Success Banner */}
      {isRecovered && (
        <div className="p-5 rounded-2xl bg-emerald-50 border border-emerald-200 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-black text-emerald-900 text-sm">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              PAYMENT RECOVERED: ${payment?.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })} Recovered
            </div>
            <p className="text-xs text-emerald-700">
              Payment was successfully captured and confirmed by the gateway. Case is terminal and closed.
            </p>
            <div className="text-[11px] font-mono text-emerald-600 mt-1">
              Status: <strong>RECOVERED</strong> • Next Action: <strong>NONE</strong>
            </div>
          </div>
        </div>
      )}

      {/* Re-evaluating Banner with Live Countdown */}
      {isReevaluating && (
        <div className="p-5 rounded-2xl bg-blue-50 border border-blue-200 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 font-black text-blue-900 text-sm">
              <Brain className="w-5 h-5 text-blue-600 animate-pulse" />
              {isFutureRetry ? 'RETRY SCHEDULED: Autonomous Recovery Backoff Active' : 'CASE RE-EVALUATING: Recovery Window Open'}
            </div>
            <p className="text-xs text-blue-700">
              {isFutureRetry
                ? 'Previous recovery attempt failed. Recovery retry is scheduled and will automatically execute when the retry window opens.'
                : 'A previous retry attempt failed. RecoverAI is reassessing the context before selecting the next recovery action.'}
            </p>
            <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-blue-800 mt-1">
              <span>Status: <strong>RE_EVALUATING</strong></span>
              <span>Attempt: <strong>{data.retry_count || 1}/3</strong></span>
              {data.retry_after && (
                <span>Next Retry: <strong>{new Date(data.retry_after).toLocaleTimeString()}</strong></span>
              )}
              {isFutureRetry && (
                <span className="px-2 py-0.5 rounded bg-blue-100 border border-blue-300 text-blue-900 font-bold">
                  Time Remaining: {formatCountdown(remainingSeconds)}
                </span>
              )}
            </div>
            {scheduleNotice && (
              <div className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200 mt-2">
                ✓ {scheduleNotice}
              </div>
            )}
          </div>

          {canMutate && (
            <button
              onClick={handleReevaluate}
              disabled={actionLoading}
              className="px-4 py-2 rounded-xl bg-blue-600 text-white font-bold text-xs hover:bg-blue-700 transition-all cursor-pointer shadow-sm"
            >
              {isFutureRetry ? 'Confirm Retry Schedule' : 'Re-evaluate Case Now'}
            </button>
          )}
        </div>
      )}


      {/* Stopped Banner */}
      {isStopped && (
        <div className="p-5 rounded-2xl bg-rose-50 border border-rose-200 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-black text-rose-900 text-sm">
              <XCircle className="w-5 h-5 text-rose-600" />
              RECOVERY STOPPED: Retries Exhausted or Policy Blocked
            </div>
            <p className="text-xs text-rose-700">
              Automated recovery was terminated to protect customer experience and policy limits.
            </p>
            <div className="text-[11px] font-mono text-rose-600 mt-1">
              Status: <strong>STOPPED</strong> • Next Action: <strong>NONE</strong>
            </div>
          </div>
        </div>
      )}


      {/* Customer Action Required Alert Banner */}
      {isCustomerAction && (
        <div className="p-5 rounded-2xl bg-orange-50/80 border border-orange-200 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-black text-orange-900 text-sm">
              <span className="w-2 h-2 rounded-full bg-orange-500 animate-ping"></span>
              CUSTOMER ACTION REQUIRED: {customer_action_info?.type || 'UPDATE_PAYMENT_METHOD'}
            </div>
            <p className="text-xs text-orange-700">
              {customer_action_info?.description || 'Customer must update their payment credentials before retry can continue.'}
            </p>
            <div className="text-[11px] font-mono text-orange-600 mt-1">
              Next Action: <strong>WAIT_FOR_CUSTOMER_ACTION</strong> • Status: <strong>{customer_action_info?.status || 'PENDING'}</strong>
            </div>
          </div>

          {canMutate && (
            <div className="flex items-center gap-2">
              {customer_action_info?.status !== 'COMPLETED' ? (
                <button
                  onClick={handleSimulateCustomerAction}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-white border border-orange-300 text-orange-800 font-bold text-xs hover:bg-orange-100 transition-all cursor-pointer shadow-sm"
                >
                  Simulate Customer Fix
                </button>
              ) : (
                <button
                  onClick={handleReevaluate}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-emerald-600 text-white font-bold text-xs hover:bg-emerald-700 transition-all cursor-pointer shadow-sm"
                >
                  Re-evaluate & Retry Now
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Case Overview Banner */}
      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white flex flex-wrap items-center justify-between gap-6">
        <div>
          <div className="text-xs text-slate-500 font-mono">Case ID: {data.id}</div>
          <h1 className="text-2xl font-black text-slate-900 mt-1">
            ${payment?.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })} {isRecovered ? 'Revenue Recovered' : 'Revenue At Risk'}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Customer: <strong className="text-slate-900">{customer?.name}</strong> • Failure Reason: <span className="text-rose-600 font-bold">{payment?.failure_reason}</span> • Next Action: <strong className="text-purple-700">{isRecovered || isStopped ? 'NONE' : (data.next_action || (isCustomerAction ? 'WAIT_FOR_CUSTOMER_ACTION' : (isEscalated ? 'HUMAN_REVIEW' : 'RETRY')))}</strong>
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          {canMutate ? (
            isRecovered || isStopped ? (
              <div className="text-xs font-mono font-bold px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-500">
                Case Terminal ({data.status}) — No Further Actions Allowed
              </div>
            ) : (
              <>
                <button
                  onClick={handleReject}
                  disabled={actionLoading || isRecovered || isStopped}
                  className="px-4 py-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold hover:bg-rose-100 disabled:opacity-40 cursor-pointer"
                >
                  Reject
                </button>
                <button
                  onClick={handleEscalate}
                  disabled={actionLoading || isRecovered || isEscalated}
                  className="px-4 py-2 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 text-xs font-bold hover:bg-purple-100 disabled:opacity-40 cursor-pointer"
                >
                  Escalate
                </button>
                <button
                  onClick={handleApprove}
                  disabled={actionLoading || isRecovered || isStopped}
                  className="btn-primary flex items-center gap-2"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Approve Action
                </button>
                <button
                  onClick={handleExecute}
                  disabled={actionLoading || isRecovered || isStopped || (isCustomerAction && customer_action_info?.status !== 'COMPLETED')}
                  className="btn-dark flex items-center gap-2 disabled:opacity-40"
                  title={isCustomerAction && customer_action_info?.status !== 'COMPLETED' ? 'Gateway retry blocked until customer action is completed' : 'Execute live run'}
                >
                  <Play className="w-4 h-4 fill-current" />
                  Execute Live Run
                </button>
              </>
            )
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
