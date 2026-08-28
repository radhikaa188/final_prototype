import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Zap,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Check
} from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const AgentExecution: React.FC = () => {
  const { caseId, runId } = useParams<{ caseId: string; runId: string }>();
  const [steps, setSteps] = useState<any[]>([]);
  const [runDetails, setRunDetails] = useState<any>(null);
  const [activeStep, setActiveStep] = useState<string>('LOAD_CONTEXT');
  const [isCompleted, setIsCompleted] = useState(false);
  const [finalResult, setFinalResult] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>('PREDICT_RECOVERY');

  const navigate = useNavigate();

  const allStepNames = [
    { name: 'LOAD_CONTEXT', label: 'Load Recovery Context' },
    { name: 'DIAGNOSE', label: 'Root Cause Rules Evaluated' },
    { name: 'PREDICT_RECOVERY', label: 'ML Recovery Prediction' },
    { name: 'REVIEW_HISTORY', label: 'Review Previous Actions' },
    { name: 'SELECT_ACTION', label: 'Select Recovery Action' },
    { name: 'CHECK_GUARDRAILS', label: 'Validate Guardrails' },
    { name: 'EXECUTE', label: 'Execute Action' },
    { name: 'OBSERVE', label: 'Observe Outcome' },
    { name: 'UPDATE_STATE', label: 'Update System State' },
    { name: 'NOTIFY', label: 'Send Notification' },
    { name: 'AUDIT', label: 'Record Audit Event' }
  ];

  useEffect(() => {
    if (!runId) return;

    api.getAgentRun(runId).then((data) => {
      setRunDetails(data);
      if (data.steps && data.steps.length > 0) {
        setSteps(data.steps);
      }
      if (data.status === 'COMPLETED' || data.status === 'BLOCKED') {
        setIsCompleted(true);
        setFinalResult(data.final_result || data.status);
      }
    });

    const eventSource = new EventSource(`/api/agent/runs/${runId}/stream`);

    eventSource.onmessage = (event) => {
      try {
        let rawData = event.data;
        if (typeof rawData === 'string' && rawData.startsWith('data: ')) {
          rawData = rawData.substring(6).trim();
        }
        const payload = JSON.parse(rawData);
        
        if (payload.event === 'COMPLETE') {
          setIsCompleted(true);
          setFinalResult(payload.final_result || 'COMPLETED');
          eventSource.close();
          return;
        }

        if (payload.step_name) {
          setActiveStep(payload.step_name);
          setSteps((prev) => {
            const existingIdx = prev.findIndex((s) => s.step_name === payload.step_name);
            if (existingIdx >= 0) {
              const updated = [...prev];
              updated[existingIdx] = { ...updated[existingIdx], ...payload };
              return updated;
            }
            return [...prev, payload];
          });
        }
      } catch (err) {
        console.error('Error parsing SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.log('SSE connection closed or completed.', err);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [runId]);

  const toggleStepExpand = (stepName: string) => {
    setExpandedStep(expandedStep === stepName ? null : stepName);
  };

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(`/recovery/${caseId}`)}
          className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Case Detail
        </button>

        <div className="flex items-center gap-3">
          {!isCompleted ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-bold animate-pulse">
              <span className="w-2 h-2 rounded-full bg-blue-600"></span>
              AGENT WORKING IN REAL-TIME
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#F0FDF4] border border-emerald-200 text-[#16A34A] text-xs font-bold">
              <CheckCircle2 className="w-4 h-4" />
              AGENT WORKFLOW COMPLETED
            </div>
          )}
        </div>
      </div>

      {/* Execution Summary Header */}
      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500 font-mono">Agent Run ID: {runId}</div>
          <h1 className="text-xl font-black text-slate-900 mt-1 flex items-center gap-3">
            Autonomous Recovery Agent Live Execution
          </h1>
          <p className="text-xs text-slate-500 mt-1">Executing multi-step deterministic intelligence pipeline with real-time SSE stream</p>
        </div>

        {isCompleted && (
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/recovery/${caseId}`)}
              className="btn-dark"
            >
              View Case
            </button>
            <button
              onClick={() => navigate('/audit')}
              className="btn-dark"
            >
              View Audit
            </button>
            <button
              onClick={() => navigate('/recovery')}
              className="btn-primary"
            >
              Back to Queue
            </button>
          </div>
        )}
      </div>

      {/* Final Outcome Banner if Completed */}
      {isCompleted && finalResult === 'RECOVERED' && (
        <div className="p-6 rounded-xl bg-[#F0FDF4] border border-emerald-200 flex items-center justify-between text-slate-900 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-emerald-100 text-[#16A34A]">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div>
              <div className="text-xs font-bold text-[#16A34A] uppercase tracking-widest font-mono">Recovery Successful</div>
              <h2 className="text-2xl font-black text-slate-900 mt-0.5">
                ${runDetails?.payment?.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })} Revenue Captured
              </h2>
              <p className="text-xs text-slate-600">Payment captured via Simulated Gateway. System state updated in Database.</p>
            </div>
          </div>
          <StatusBadge status="RECOVERED" />
        </div>
      )}

      {/* Step Timeline Cards */}
      <div className="space-y-4">
        {allStepNames.map((sObj, idx) => {
          const stepData = steps.find((s) => s.step_name === sObj.name);
          const isCurrent = activeStep === sObj.name && !isCompleted;
          const isDone = stepData?.status === 'SUCCESS';
          const isBlocked = stepData?.status === 'BLOCKED';
          const isExpanded = expandedStep === sObj.name;

          let outputObj: any = {};
          try {
            if (stepData?.output_summary) {
              outputObj = typeof stepData.output_summary === 'string' ? JSON.parse(stepData.output_summary) : stepData.output_summary;
            } else if (stepData?.output) {
              outputObj = stepData.output;
            }
          } catch (e) {}

          return (
            <div
              key={sObj.name}
              className={`glass-panel rounded-xl border transition-all duration-200 ${
                isCurrent
                  ? 'border-purple-300 bg-purple-50/40 shadow-sm'
                  : isDone
                  ? 'border-slate-200 bg-white'
                  : isBlocked
                  ? 'border-rose-200 bg-rose-50/40'
                  : 'border-slate-100 bg-slate-50/50 opacity-60'
              }`}
            >
              {/* Step Header Bar */}
              <div
                onClick={() => toggleStepExpand(sObj.name)}
                className="p-4 flex items-center justify-between cursor-pointer select-none"
              >
                <div className="flex items-center gap-4">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs font-mono">
                    {isDone ? (
                      <div className="w-7 h-7 rounded-lg bg-[#F0FDF4] border border-emerald-200 text-[#16A34A] flex items-center justify-center">
                        <Check className="w-4 h-4" />
                      </div>
                    ) : isBlocked ? (
                      <div className="w-7 h-7 rounded-lg bg-[#FEF2F2] border border-rose-200 text-[#DC2626] flex items-center justify-center">
                        <AlertTriangle className="w-4 h-4" />
                      </div>
                    ) : isCurrent ? (
                      <div className="w-7 h-7 rounded-lg bg-purple-100 border border-purple-300 text-purple-700 flex items-center justify-center animate-spin">
                        <Zap className="w-4 h-4" />
                      </div>
                    ) : (
                      <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center text-xs font-mono">
                        {idx + 1}
                      </div>
                    )}
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      {sObj.label}
                      {isCurrent && <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-mono font-bold">EXECUTING</span>}
                    </h3>
                    <p className="text-xs text-slate-500">{stepData?.input_summary || 'Pending execution...'}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {stepData?.timestamp && (
                    <span className="text-[10px] font-mono text-slate-400 hidden sm:inline">
                      {new Date(stepData.timestamp).toLocaleTimeString()}
                    </span>
                  )}
                  {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                </div>
              </div>

              {/* Expandable Step Payload */}
              {isExpanded && (
                <div className="p-4 border-t border-slate-100 bg-slate-50/80 rounded-b-xl text-xs space-y-3">
                  {sObj.name === 'PREDICT_RECOVERY' && outputObj.recovery_probability !== undefined && (
                    <div className="p-4 rounded-xl bg-white border border-slate-200 grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-[10px] text-slate-500 font-mono uppercase">ML Prediction Score</div>
                        <div className="text-xl font-black text-emerald-600 mt-1">{(outputObj.recovery_probability * 100).toFixed(0)}% P(Recovery)</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500 font-mono uppercase">Expected Recoverable Revenue</div>
                        <div className="text-xl font-black text-purple-700 mt-1">${outputObj.expected_recovery?.toLocaleString()}</div>
                      </div>
                    </div>
                  )}

                  {sObj.name === 'SELECT_ACTION' && outputObj.action && (
                    <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-slate-900">Recommended Action:</span>
                        <StatusBadge status={outputObj.action} type="action" />
                      </div>
                      <p className="text-slate-700 text-xs">{outputObj.reason}</p>
                      <div className="text-[10px] font-mono text-slate-500">Agent Confidence: {((outputObj.confidence || 0.85)*100).toFixed(0)}%</div>
                    </div>
                  )}

                  {sObj.name === 'CHECK_GUARDRAILS' && outputObj.checks && (
                    <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-2">
                      <div className="font-bold text-purple-700 flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4" />
                        {outputObj.allowed ? 'ACTION ALLOWED BY GUARDRAILS' : 'ACTION BLOCKED BY POLICY'}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                        {Object.entries(outputObj.checks).map(([k, v]: [string, any]) => (
                          <div key={k} className="flex justify-between text-slate-700 border-b border-slate-100 pb-1">
                            <span>{k.replace('_', ' ')}:</span>
                            <span className={v.passed ? 'text-emerald-600 font-bold' : 'text-rose-600 font-bold'}>{v.passed ? 'PASSED' : 'BLOCKED'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Clean Code Output Display */}
                  <pre className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px] font-mono text-purple-300 overflow-x-auto">
                    {JSON.stringify(outputObj, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
