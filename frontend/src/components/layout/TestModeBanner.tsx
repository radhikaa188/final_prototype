import React, { useState } from 'react';
import { Sparkles, FlaskConical, ArrowRight, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';

export const TestModeBanner: React.FC = () => {
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleGeneratePayment = async () => {
    try {
      setLoading(true);
      const res = await api.generateTestPayment();
      if (res.case_id) {
        navigate(`/recovery/${res.case_id}`);
      }
    } catch (err) {
      console.error('Failed to generate test payment:', err);
    } finally {
      setLoading(false);
    }
  };

  if (dismissed) return null;

  return (
    <div className="bg-[#FEF3E2] border-b border-amber-200/80 px-8 py-2 flex items-center justify-between text-xs text-amber-900 shrink-0">
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold border border-amber-300 uppercase tracking-widest text-[10px]">
          <FlaskConical className="w-3.5 h-3.5" />
          TEST MODE
        </span>
        <span className="text-amber-900 hidden md:inline">
          Connected to <strong className="font-semibold text-amber-950">Database</strong> & <strong className="font-semibold text-amber-950">Simulated Payment Gateway</strong>.
        </span>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleGeneratePayment}
          disabled={loading}
          className="btn-primary flex items-center gap-2 py-1 px-3 text-xs"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {loading ? 'Ingesting Event...' : 'Generate Test Payment'}
          <ArrowRight className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => setDismissed(true)}
          className="p-1 rounded text-amber-700 hover:text-amber-950 hover:bg-amber-100 transition-colors cursor-pointer"
          title="Dismiss Banner"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
