import React, { useEffect, useState } from 'react';
import { Save, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';

export const Policies: React.FC = () => {
  const [policy, setPolicy] = useState<any>({
    max_retries: 3,
    recovery_window_hours: 72,
    max_auto_retry_amount: 10000.0,
    customer_opt_out_enabled: true,
    duplicate_action_protection: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    async function loadPol() {
      try {
        setLoading(true);
        const data = await api.getPolicy();
        if (data) setPolicy(data);
      } catch (err) {
        console.error('Failed to load policy:', err);
      } finally {
        setLoading(false);
      }
    }
    loadPol();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      const res = await api.updatePolicy(policy);
      setPolicy(res);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to save policy:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-500 font-mono text-xs">Loading operational policy config...</div>;
  }

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Policies &amp; Operational Guardrails
        </h1>
        <p className="text-xs text-slate-500 mt-1">Configure business rules that govern the Recovery Agent's execution boundaries in Database</p>
      </div>

      <form onSubmit={handleSave} className="glass-panel p-8 rounded-xl border border-slate-200 bg-white space-y-6">
        {savedSuccess && (
          <div className="p-4 rounded-xl bg-[#F0FDF4] border border-emerald-200 text-[#16A34A] text-xs font-bold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            Operational policies updated and persisted to Database!
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-900 mb-1">Maximum Retry Count</label>
            <p className="text-[11px] text-slate-500 mb-2">Maximum number of automated payment retry attempts per recovery case before stopping or escalating.</p>
            <input
              type="number"
              value={policy.max_retries}
              onChange={(e) => setPolicy({ ...policy, max_retries: parseInt(e.target.value) || 1 })}
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-900 font-mono focus:outline-none focus:border-purple-500"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-900 mb-1">Recovery Window (Hours)</label>
            <p className="text-[11px] text-slate-500 mb-2">Time limit in hours after payment failure within which recovery actions remain eligible.</p>
            <input
              type="number"
              value={policy.recovery_window_hours}
              onChange={(e) => setPolicy({ ...policy, recovery_window_hours: parseInt(e.target.value) || 24 })}
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-900 font-mono focus:outline-none focus:border-purple-500"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-900 mb-1">Maximum Automatic Retry Amount ($)</label>
            <p className="text-[11px] text-slate-500 mb-2">Transactions exceeding this dollar threshold require manual human approval.</p>
            <input
              type="number"
              value={policy.max_auto_retry_amount}
              onChange={(e) => setPolicy({ ...policy, max_auto_retry_amount: parseFloat(e.target.value) || 100 })}
              className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs text-slate-900 font-mono focus:outline-none focus:border-purple-500"
            />
          </div>

          <div className="pt-2 space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={policy.customer_opt_out_enabled}
                onChange={(e) => setPolicy({ ...policy, customer_opt_out_enabled: e.target.checked })}
                className="w-4 h-4 rounded border-slate-300 text-purple-600 focus:ring-0 cursor-pointer"
              />
              <div>
                <div className="text-xs font-bold text-slate-900">Enforce Customer Opt-Out Protection</div>
                <div className="text-[11px] text-slate-500">Automatically block retries and nudges for customers who opted out.</div>
              </div>
            </label>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={policy.duplicate_action_protection}
                onChange={(e) => setPolicy({ ...policy, duplicate_action_protection: e.target.checked })}
                className="w-4 h-4 rounded border-slate-300 text-purple-600 focus:ring-0 cursor-pointer"
              />
              <div>
                <div className="text-xs font-bold text-slate-900">Enforce Duplicate Action Protection</div>
                <div className="text-[11px] text-slate-500">Prevent repeating the exact same failed action without customer state change.</div>
              </div>
            </label>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="btn-primary w-full py-3 flex items-center justify-center gap-2 font-bold text-xs"
        >
          <Save className="w-4 h-4" />
          {saving ? 'Saving to Database...' : 'Save & Enforce Policy Changes'}
        </button>
      </form>
    </div>
  );
};
