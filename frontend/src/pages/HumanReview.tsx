import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Play } from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const HumanReview: React.FC = () => {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchHumanReviewCases = async () => {
    try {
      setLoading(true);
      const res = await api.getRecoveryCases({ status: 'NEEDS_REVIEW' });
      setCases(res.cases || []);
    } catch (err) {
      console.error('Failed to load human review cases:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHumanReviewCases();
  }, []);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Human Review Operations Queue
          <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
            {cases.length} Escalated Cases
          </span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">Cases escalated due to high transaction value, risk restrictions, or automated policy limits</p>
      </div>

      <div className="space-y-4">
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-xs font-mono">Loading escalated cases...</div>
        ) : cases.length === 0 ? (
          <div className="glass-panel p-12 rounded-xl border border-slate-200 bg-white text-center space-y-3">
            <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto" />
            <h3 className="text-sm font-bold text-slate-900">No Pending Escalated Cases</h3>
            <p className="text-xs text-slate-500">All recovery cases are operating smoothly under automated guardrails.</p>
          </div>
        ) : (
          cases.map((item) => (
            <div key={item.id} className="glass-panel p-6 rounded-xl border border-slate-200 bg-white flex flex-wrap items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-purple-700 font-bold">#{item.priority}</span>
                  <span className="text-sm font-bold text-slate-900">{item.customer_name}</span>
                  <StatusBadge status={item.status} />
                </div>
                <div className="text-xs text-slate-500 mt-2 space-x-4 font-mono">
                  <span>Amount: <strong className="text-slate-900">${item.amount?.toLocaleString()}</strong></span>
                  <span>P(Recovery): <strong className="text-emerald-600">{(item.recovery_probability * 100).toFixed(0)}%</strong></span>
                  <span>Reason: <strong className="text-rose-600">{item.failure_reason}</strong></span>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => navigate(`/recovery/${item.id}`)}
                  className="btn-dark"
                >
                  Review Case Detail
                </button>
                <button
                  onClick={async () => {
                    const res = await api.approveCase(item.id);
                    if (res.run_id) navigate(`/recovery/${item.id}/run/${res.run_id}`);
                  }}
                  className="btn-primary flex items-center gap-2"
                >
                  <Play className="w-4 h-4 fill-current" />
                  Approve &amp; Execute
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
