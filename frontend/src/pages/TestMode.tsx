import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, FlaskConical, ArrowRight, CheckCircle2, Play, AlertTriangle } from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const TestMode: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [lastGenerated, setLastGenerated] = useState<any>(null);
  const [customAmount, setCustomAmount] = useState<number>(149.99);
  const [customReason, setCustomReason] = useState<string>('INSUFFICIENT_FUNDS');
  const navigate = useNavigate();

  const handleGeneratePayment = async (amountOverride?: number, reasonOverride?: string) => {
    try {
      setLoading(true);
      const payload: any = {};
      if (amountOverride) payload.amount = amountOverride;
      if (reasonOverride) payload.failure_reason = reasonOverride;

      const res = await api.generateTestPayment(payload);
      setLastGenerated(res);
    } catch (err) {
      console.error('Failed to generate test payment:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Test Mode Event Simulator
          <span className="text-xs px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 font-mono border border-amber-300 font-bold uppercase">
            Synthetic Telemetry Sandbox
          </span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Simulate real-time payment failure events, trigger automated ML intelligence predictions, and test end-to-end agent recovery execution.
        </p>
      </div>

      {/* Primary Simulator Card */}
      <div className="glass-panel p-8 rounded-xl border border-slate-200 bg-white space-y-6">
        <div className="flex items-center justify-between pb-6 border-b border-slate-100">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-purple-600" />
              Instant Event Generator
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Generates a synthetic payment failure event and initializes a prioritized recovery case.
            </p>
          </div>

          <button
            onClick={() => handleGeneratePayment()}
            disabled={loading}
            className="btn-primary flex items-center gap-2 px-5 py-2.5 text-sm"
          >
            <Sparkles className="w-4 h-4" />
            {loading ? 'Ingesting Event...' : 'Generate Random Failed Payment'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Custom Event Creator Form */}
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider">
            Custom Event Configuration
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Transaction Amount ($)</label>
              <input
                type="number"
                value={customAmount}
                onChange={(e) => setCustomAmount(parseFloat(e.target.value) || 10.0)}
                className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-900 font-mono focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Payment Failure Reason</label>
              <select
                value={customReason}
                onChange={(e) => setCustomReason(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-900 focus:outline-none focus:border-purple-500 cursor-pointer"
              >
                <option value="TRANSIENT_TIMEOUT">TRANSIENT_TIMEOUT (88% Historical Recovery)</option>
                <option value="GATEWAY_ERROR">GATEWAY_ERROR (87% Historical Recovery)</option>
                <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS (73% Historical Recovery)</option>
                <option value="CARD_DECLINED">CARD_DECLINED (64% Historical Recovery)</option>
                <option value="CARD_EXPIRED">CARD_EXPIRED (58% Historical Recovery)</option>
                <option value="FRAUD_RISK">FRAUD_RISK (38% Historical Recovery)</option>
                <option value="ACCOUNT_CLOSED">ACCOUNT_CLOSED (15% Historical Recovery)</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={() => handleGeneratePayment(customAmount, customReason)}
                disabled={loading}
                className="btn-dark w-full py-2.5 flex items-center justify-center gap-2"
              >
                <Play className="w-4 h-4 fill-current" />
                Ingest Custom Event
              </button>
            </div>
          </div>
        </div>

        {/* Display Last Generated Event Result */}
        {lastGenerated && (
          <div className="p-6 rounded-xl bg-purple-50/60 border border-purple-200 space-y-4 pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-purple-900 font-bold text-xs">
                <CheckCircle2 className="w-4 h-4 text-purple-600" />
                Payment Failure Event Ingested Successfully!
              </div>
              <button
                onClick={() => navigate(`/recovery/${lastGenerated.case_id}`)}
                className="btn-primary flex items-center gap-1.5 py-1 px-3 text-xs"
              >
                View Created Case
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
              <div className="p-3 rounded-lg bg-white border border-purple-100">
                <div className="text-[10px] text-slate-500 uppercase">Customer</div>
                <div className="font-bold text-slate-900 mt-0.5">{lastGenerated.customer_name}</div>
              </div>
              <div className="p-3 rounded-lg bg-white border border-purple-100">
                <div className="text-[10px] text-slate-500 uppercase">Amount</div>
                <div className="font-bold text-slate-900 mt-0.5">${lastGenerated.amount?.toLocaleString()}</div>
              </div>
              <div className="p-3 rounded-lg bg-white border border-purple-100">
                <div className="text-[10px] text-slate-500 uppercase">P(Recovery) Score</div>
                <div className="font-bold text-emerald-600 mt-0.5">{((lastGenerated.recovery_probability || 0.5) * 100).toFixed(0)}%</div>
              </div>
              <div className="p-3 rounded-lg bg-white border border-purple-100">
                <div className="text-[10px] text-slate-500 uppercase">Recommended Action</div>
                <div className="mt-0.5">
                  <StatusBadge status={lastGenerated.recommended_action || 'RETRY'} type="action" />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
