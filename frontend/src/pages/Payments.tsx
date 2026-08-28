import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const Payments: React.FC = () => {
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    async function loadPay() {
      try {
        setLoading(true);
        const res = await api.getPayments();
        setPayments(res.payments || []);
      } catch (err) {
        console.error('Failed to load payments:', err);
      } finally {
        setLoading(false);
      }
    }
    loadPay();
  }, []);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Payment Event Ledger
          <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
            {payments.length} Transactions
          </span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">Complete payment attempt logs ingested from payment gateway webhooks and test simulator</p>
      </div>

      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-xs font-mono">Loading payment ledger...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-3.5 pl-3">Payment ID</th>
                  <th className="py-3.5">Gateway Payment ID</th>
                  <th className="py-3.5">Customer</th>
                  <th className="py-3.5">Amount</th>
                  <th className="py-3.5">Failure Reason</th>
                  <th className="py-3.5">Attempt</th>
                  <th className="py-3.5 pr-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {payments.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => p.recovery_case_id ? navigate(`/recovery/${p.recovery_case_id}`) : null}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 pl-3 font-mono text-purple-700 font-bold">{p.id.substring(0, 8)}...</td>
                    <td className="py-3.5 font-mono text-slate-700">{p.gateway_payment_id}</td>
                    <td className="py-3.5 font-bold text-slate-900">{p.customer_name}</td>
                    <td className="py-3.5 font-mono font-bold text-slate-900">${p.amount?.toLocaleString()}</td>
                    <td className="py-3.5 font-mono text-rose-600 font-bold">{p.failure_reason || 'N/A'}</td>
                    <td className="py-3.5 font-mono text-slate-700">#{p.attempt_number}</td>
                    <td className="py-3.5 pr-3"><StatusBadge status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
