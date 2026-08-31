import React, { useEffect, useState } from 'react';
import { 
  CheckCircle2, 
  Play, 
  AlertTriangle, 
  XCircle, 
  ShieldCheck, 
  User, 
  Brain, 
  History, 
  ChevronRight
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';
import { useAuth } from '../auth/AuthContext';

export const HumanReview: React.FC = () => {
  const { role } = useAuth();
  const canApprove = role === 'OPS' || role === 'ADMIN';

  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Selection & Detail States
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  
  // Interactive action selection
  const [approvedAction, setApprovedAction] = useState<string>('RETRY');
  const [actionLoading, setActionLoading] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);

  const fetchHumanReviewCases = async (selectFirst = false) => {
    try {
      setLoading(true);
      const res = await api.getRecoveryCases({ status: 'NEEDS_REVIEW' });
      const fetchedCases = res.cases || [];
      setCases(fetchedCases);
      
      // If requested and we have cases, select the first case automatically
      if (selectFirst && fetchedCases.length > 0) {
        setSelectedId(fetchedCases[0].id);
      }
    } catch (err) {
      console.error('Failed to load human review cases:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHumanReviewCases(true);
  }, []);

  // Fetch detail when selected case changes
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setExecutionResult(null);
      return;
    }

    const fetchDetail = async () => {
      try {
        setLoadingDetail(true);
        setExecutionResult(null);
        const data = await api.getRecoveryCase(selectedId);
        setDetail(data);
        
        // Default approved action to recommended action if valid, or default to RETRY
        const mlRec = data.agent_decision?.recommended_action || 'RETRY';
        setApprovedAction(mlRec === 'HUMAN_REVIEW' || mlRec === 'STOP' ? 'RETRY' : mlRec);
      } catch (err) {
        console.error('Failed to fetch case details:', err);
      } finally {
        setLoadingDetail(false);
      }
    };

    fetchDetail();
  }, [selectedId]);

  const handleApprove = async () => {
    if (!selectedId) return;
    try {
      setActionLoading(true);
      const res = await api.approveCase(selectedId, approvedAction);
      setExecutionResult(res);
    } catch (err: any) {
      console.error('Failed to approve case:', err);
      alert(`Approval error: ${err.message || err}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedId) return;
    const confirmReject = window.confirm('Are you sure you want to reject this recovery? This will stop further recovery attempts.');
    if (!confirmReject) return;

    try {
      setActionLoading(true);
      const res = await api.rejectCase(selectedId);
      setExecutionResult({
        status: 'STOPPED',
        final_result: 'STOPPED',
        case_status: 'STOPPED',
        payment_status: 'FAILED',
        approved_action: approvedAction,
        rejected: true
      });
    } catch (err: any) {
      console.error('Failed to reject case:', err);
      alert(`Rejection error: ${err.message || err}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDismissResult = () => {
    // Clear states and reload queue
    setExecutionResult(null);
    setDetail(null);
    setSelectedId(null);
    fetchHumanReviewCases(true);
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto h-[calc(100vh-64px)] flex flex-col">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Human Review Operations Queue
          <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
            {cases.length} Escalated Cases
          </span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">Cases escalated due to high transaction value, risk restrictions, or automated policy limits</p>
      </div>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Left Column: Queue List */}
        <div className="col-span-4 flex flex-col min-h-0 bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-4 bg-slate-50 border-b border-slate-200">
            <span className="text-xs font-mono font-bold text-slate-500 uppercase tracking-wider">Escalated Queue</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {loading && cases.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs font-mono">Loading queue...</div>
            ) : cases.length === 0 ? (
              <div className="p-8 text-center space-y-3 flex-1 flex flex-col justify-center">
                <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto animate-bounce" />
                <h3 className="text-xs font-bold text-slate-900 mt-2">No Escalated Cases</h3>
                <p className="text-[10px] text-slate-500">All cases operating smoothly.</p>
              </div>
            ) : (
              cases.map((c) => {
                const isSelected = selectedId === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedId(c.id)}
                    className={`p-4 cursor-pointer transition-all flex justify-between items-center gap-3 hover:bg-slate-50/80 ${
                      isSelected ? 'bg-purple-50/50 border-r-4 border-purple-600' : ''
                    }`}
                  >
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-950 truncate max-w-[140px]">{c.customer_name}</span>
                        <StatusBadge status={c.status} />
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 flex justify-between items-center">
                        <span>Amount: <strong>${c.amount?.toLocaleString()}</strong></span>
                        <span>Prob: <strong className="text-emerald-600">{(c.recovery_probability * 100).toFixed(0)}%</strong></span>
                      </div>
                    </div>
                    <ChevronRight className={`w-4 h-4 text-slate-400 shrink-0 transition-transform ${isSelected ? 'translate-x-1 text-purple-600' : ''}`} />
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Case Review Detail Panel */}
        <div className="col-span-8 flex flex-col min-h-0 bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
          {loadingDetail ? (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-xs font-mono">
              Loading escalated case details...
            </div>
          ) : !detail ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-3 bg-slate-50/50">
              <Brain className="w-12 h-12 text-slate-300 animate-pulse" />
              <h3 className="text-sm font-bold text-slate-955">Select Case to Begin Review</h3>
              <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                Choose an escalated case from the left panel to review telemetry, ML recommendations, policy guardrails, and execute recovery.
              </p>
            </div>
          ) : executionResult ? (
            /* Terminal Result Display Panel */
            <div className="flex-1 overflow-y-auto p-8 space-y-6">
              {executionResult.rejected ? (
                /* Rejection View */
                <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-slate-200 text-slate-700 rounded-xl">
                      <Ban className="w-8 h-8" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-slate-900">Recovery Attempt Rejected</h3>
                      <p className="text-xs text-slate-500">The recovery action was explicitly stopped by the employee.</p>
                    </div>
                  </div>
                  <div className="p-4 bg-white rounded-lg border border-slate-200 space-y-2 text-xs font-mono">
                    <div>Approved Action: <strong className="text-slate-800">{executionResult.approved_action}</strong></div>
                    <div>Case Status: <strong className="text-rose-700">{executionResult.case_status}</strong></div>
                    <div>Payment Status: <strong className="text-slate-800">{executionResult.payment_status}</strong></div>
                    <div>Gateway Status: <strong className="text-slate-500">NO ATTEMPTED GATEWAY CALLS</strong></div>
                  </div>
                </div>
              ) : executionResult.case_status === 'RECOVERED' ? (
                /* Successful Recovery View */
                <div className="p-6 bg-[#F0FDF4] border border-emerald-200 rounded-xl space-y-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-emerald-100 text-emerald-600 rounded-xl">
                      <CheckCircle2 className="w-8 h-8" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-emerald-900">✓ Recovery Successful</h3>
                      <p className="text-xs text-emerald-700 font-medium">The gateway captures were successful and database updated.</p>
                    </div>
                  </div>
                  <div className="p-4 bg-white rounded-lg border border-emerald-100 space-y-2 text-xs font-mono">
                    <div>Approved Action: <strong className="text-slate-800">{executionResult.approved_action}</strong></div>
                    <div>Gateway: <strong className="text-emerald-600">SUCCESS</strong></div>
                    <div>Payment: <strong className="text-emerald-600">SUCCESS</strong></div>
                    <div>Case Status: <strong className="text-emerald-600">RECOVERED</strong></div>
                    <div>Recovered Amount: <strong className="text-slate-900 text-sm font-bold">${executionResult.amount_recovered?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></div>
                  </div>
                </div>
              ) : executionResult.run_status === 'BLOCKED' || executionResult.case_status === 'STOPPED' ? (
                /* Blocked Recovery View */
                <div className="p-6 bg-amber-50 border border-amber-200 rounded-xl space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-amber-100 text-amber-600 rounded-xl">
                      <AlertTriangle className="w-8 h-8" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-amber-900">⚠ Action Blocked</h3>
                      <p className="text-xs text-amber-700 font-medium">The action was denied execution by deterministic policy guardrails.</p>
                    </div>
                  </div>
                  <div className="p-4 bg-white rounded-lg border border-amber-100 space-y-2 text-xs font-mono">
                    <div>Approved Action: <strong className="text-slate-800">{executionResult.approved_action}</strong></div>
                    <div>Reason: <strong className="text-rose-600">{executionResult.final_result || 'Blocked by Policy Guardrails'}</strong></div>
                    <div>Payment: <strong className="text-amber-600">FAILED</strong></div>
                    <div>Case Status: <strong className="text-amber-600">{executionResult.case_status}</strong></div>
                  </div>
                </div>
              ) : (
                /* Failed Recovery View */
                <div className="p-6 bg-rose-50 border border-rose-200 rounded-xl space-y-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-rose-100 text-rose-600 rounded-xl">
                      <XCircle className="w-8 h-8" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-rose-900">✕ Recovery Attempt Failed</h3>
                      <p className="text-xs text-rose-700 font-medium">The gateway retry failed. State reverted to failure/re-evaluation queue.</p>
                    </div>
                  </div>
                  <div className="p-4 bg-white rounded-lg border border-rose-100 space-y-2 text-xs font-mono">
                    <div>Approved Action: <strong className="text-slate-800">{executionResult.approved_action}</strong></div>
                    <div>Gateway: <strong className="text-rose-600">FAILED</strong></div>
                    <div>Payment: <strong className="text-rose-600">FAILED</strong></div>
                    <div>Case Status: <strong className="text-rose-600">{executionResult.case_status}</strong></div>
                  </div>
                </div>
              )}

              <div className="flex justify-end pt-4">
                <button
                  onClick={handleDismissResult}
                  className="btn-primary px-6"
                >
                  Acknowledge &amp; Return to Queue
                </button>
              </div>
            </div>
          ) : (
            /* Case Telemetry Review View */
            <div className="flex-1 flex flex-col min-h-0">
              <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                <div>
                  <span className="text-[10px] font-mono text-slate-400">Escalated Case #{detail.id.substring(0, 8)}</span>
                  <h2 className="text-base font-bold text-slate-900 mt-0.5">{detail.customer?.name}</h2>
                </div>
                <StatusBadge status={detail.status} />
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* 1. Reason for Review & Basic Context */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="text-[10px] text-slate-400 font-mono uppercase font-bold">Reason for Review</div>
                    <p className="text-xs font-bold text-rose-600 mt-1">{detail.payment?.failure_reason || 'Manual Review Required'}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="text-[10px] text-slate-400 font-mono uppercase font-bold">Payment Amount &amp; Status</div>
                    <p className="text-xs font-bold text-slate-900 mt-1">
                      ${detail.payment?.amount?.toLocaleString()} {detail.payment?.currency}
                      <span className="ml-2 text-[10px] px-2 py-0.5 rounded bg-rose-100 text-rose-700 uppercase font-mono font-bold">
                        {detail.payment?.status}
                      </span>
                    </p>
                  </div>
                </div>

                {/* 2. Customer context */}
                <div className="space-y-2">
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    Customer Profile
                  </span>
                  <div className="p-4 rounded-xl border border-slate-200 space-y-1.5 text-xs">
                    <div className="flex justify-between"><span className="text-slate-500">Email:</span><strong className="text-slate-900">{detail.customer?.email}</strong></div>
                    <div className="flex justify-between"><span className="text-slate-500">LTV:</span><strong className="text-slate-900">${detail.customer?.lifetime_value?.toLocaleString()}</strong></div>
                    <div className="flex justify-between"><span className="text-slate-500">Customer Since:</span><strong className="text-slate-900">{detail.customer?.customer_since ? new Date(detail.customer.customer_since).toLocaleDateString() : 'N/A'}</strong></div>
                  </div>
                </div>

                {/* 3. ML Intelligence & Probabilities */}
                <div className="space-y-2">
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <Brain className="w-3.5 h-3.5 text-purple-500" />
                    ML Recovery Intelligence
                  </span>
                  <div className="p-4 rounded-xl border border-slate-200 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-[10px] text-slate-400 font-mono uppercase">ML Recommended Action</span>
                        <div className="text-sm font-bold text-purple-700 mt-0.5">{detail.agent_decision?.recommended_action}</div>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 font-mono uppercase">Recovery Probability</span>
                        <div className="text-sm font-bold text-emerald-600 mt-0.5">{(detail.ml_intelligence?.recovery_probability * 100).toFixed(1)}%</div>
                      </div>
                    </div>

                    {/* Action Probabilities Breakdown List */}
                    {detail.ml_intelligence?.probabilities && (
                      <div className="space-y-2 border-t border-slate-100 pt-3">
                        <span className="text-[10px] font-mono text-slate-400 uppercase font-bold block">Action Probabilities Breakdown</span>
                        <div className="space-y-1.5 text-[11px]">
                          {Object.entries(detail.ml_intelligence.probabilities).map(([act, val]: [string, any]) => (
                            <div key={act} className="flex items-center justify-between">
                              <span className="font-mono text-slate-600">{act}</span>
                              <div className="flex items-center gap-2 flex-1 max-w-[200px] ml-4">
                                <div className="h-1.5 bg-slate-100 rounded-full flex-1 overflow-hidden">
                                  <div className="h-full bg-purple-600 rounded-full" style={{ width: `${val * 100}%` }}></div>
                                </div>
                                <span className="font-bold text-slate-800 w-10 text-right">{(val * 100).toFixed(0)}%</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* 4. Guardrail checks details */}
                <div className="space-y-2">
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-amber-500" />
                    Deterministic Policy Guardrail Checks
                  </span>
                  <div className="p-4 rounded-xl border border-slate-200 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-slate-900">Pre-execution Guardrail:</span>
                      <span className={`text-xs font-bold ${detail.guardrail_result?.allowed ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {detail.guardrail_result?.allowed ? 'PASSED (ALLOWED)' : 'BLOCKED'}
                      </span>
                    </div>
                    {detail.guardrail_result?.checks && (
                      <div className="grid grid-cols-2 gap-2 text-[11px] pt-1.5 border-t border-slate-100">
                        {Object.entries(detail.guardrail_result.checks).map(([k, v]: [string, any]) => (
                          <div key={k} className="flex justify-between text-slate-600">
                            <span>{k.replace(/_/g, ' ')}:</span>
                            <span className={v.passed ? 'text-emerald-600 font-bold' : 'text-rose-600 font-bold'}>
                              {v.passed ? 'PASSED' : 'BLOCKED'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* 5. Audit History Timeline */}
                <div className="space-y-2">
                  <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
                    <History className="w-3.5 h-3.5 text-slate-400" />
                    Timeline Audit Logs
                  </span>
                  <div className="p-4 rounded-xl border border-slate-200 font-mono text-[10px] space-y-2 max-h-[160px] overflow-y-auto bg-slate-50">
                    {detail.timeline && detail.timeline.length > 0 ? (
                      detail.timeline
                        .slice()
                        .sort((a: any, b: any) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
                        .map((evt: any, idx: number) => (
                          <div key={idx} className="pb-2 border-b border-slate-200/50 last:border-0">
                            <div className="flex justify-between text-slate-400">
                              <span>[{evt.actor}] {evt.event}</span>
                              <span>{new Date(evt.timestamp).toLocaleString()}</span>
                            </div>
                            <p className="text-slate-700 mt-0.5">{evt.description}</p>
                          </div>
                        ))
                    ) : (
                      <div className="text-slate-400 text-center py-2">No timeline logs found</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Approval Select / Footer Bar */}
              <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap gap-4 items-center justify-between">
                <div className="flex items-center gap-3">
                  <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">Approved Action:</label>
                  <select
                    value={approvedAction}
                    onChange={(e) => setApprovedAction(e.target.value)}
                    disabled={actionLoading || !canApprove}
                    className="p-2 border border-slate-300 rounded-lg text-xs bg-white text-slate-800 font-bold outline-none cursor-pointer focus:ring-1 focus:ring-purple-500 disabled:bg-slate-100 disabled:cursor-not-allowed"
                  >
                    <option value="RETRY">RETRY</option>
                    <option value="CUSTOMER_NUDGE">CUSTOMER_NUDGE</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  {canApprove ? (
                    <>
                      <button
                        onClick={handleReject}
                        disabled={actionLoading}
                        className="btn-outline border-rose-300 text-rose-700 hover:bg-rose-50 flex items-center gap-1.5 cursor-pointer"
                      >
                        <XCircle className="w-4 h-4" />
                        Reject Recovery
                      </button>
                      <button
                        onClick={handleApprove}
                        disabled={actionLoading}
                        className="btn-primary flex items-center gap-2 cursor-pointer"
                      >
                        <Play className="w-4 h-4 fill-current" />
                        Approve &amp; Execute {approvedAction}
                      </button>
                    </>
                  ) : (
                    <div className="text-xs text-slate-400 font-bold px-3 py-1.5 rounded-lg bg-slate-200 border border-slate-300 cursor-not-allowed">
                      Approval Restricted (OPS / ADMIN Required)
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const Ban: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <circle cx="12" cy="12" r="10" />
    <path d="m4.9 4.9 14.2 14.2" />
  </svg>
);
