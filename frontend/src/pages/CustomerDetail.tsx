import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CreditCard, History } from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const CustomerDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [customer, setCustomer] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    async function loadDetail() {
      try {
        setLoading(true);
        const res = await api.getCustomer(id);
        setCustomer(res);
      } catch (err) {
        console.error('Failed to load customer detail:', err);
      } finally {
        setLoading(false);
      }
    }
    loadDetail();
  }, [id]);

  if (loading || !customer) {
    return <div className="p-8 text-center text-slate-500 font-mono text-xs">Loading customer 360 profile...</div>;
  }

  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto">
      <button
        onClick={() => navigate('/customers')}
        className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-900 transition-colors cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Customers
      </button>

      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white flex items-center justify-between">
        <div>
          <div className="text-xs font-mono text-purple-700 font-bold">Customer ID: {customer.external_customer_id}</div>
          <h1 className="text-2xl font-black text-slate-900 mt-1">{customer.name}</h1>
          <p className="text-xs text-slate-500 mt-1">{customer.email} • {customer.phone}</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500 uppercase font-mono">Lifetime Value</div>
          <div className="text-2xl font-black text-emerald-600 font-mono mt-1">${customer.lifetime_value?.toLocaleString()}</div>
        </div>
      </div>

      {/* Tables Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Payment History */}
        <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-purple-600" />
            Payment History
          </h2>
          <div className="space-y-2">
            {customer.payment_history?.map((p: any) => (
              <div key={p.id} className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
                <div>
                  <div className="font-mono text-slate-900 font-bold">${p.amount?.toLocaleString()}</div>
                  <div className="text-[10px] text-slate-500">{p.failure_reason || 'Successful Charge'}</div>
                </div>
                <StatusBadge status={p.status} />
              </div>
            ))}
          </div>
        </div>

        {/* Recovery History */}
        <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <History className="w-4 h-4 text-purple-600" />
            Recovery History
          </h2>
          <div className="space-y-2">
            {customer.recovery_history?.map((r: any) => (
              <div
                key={r.id}
                onClick={() => navigate(`/recovery/${r.id}`)}
                className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs cursor-pointer hover:border-purple-300 transition-all"
              >
                <div>
                  <div className="font-mono text-purple-700 font-bold">${r.revenue_at_risk?.toLocaleString()} At Risk</div>
                  <div className="text-[10px] text-slate-500">Root Cause: {r.root_cause}</div>
                </div>
                <StatusBadge status={r.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
