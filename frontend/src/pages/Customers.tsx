import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const Customers: React.FC = () => {
  const [customers, setCustomers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    async function loadCust() {
      try {
        setLoading(true);
        const res = await api.getCustomers();
        setCustomers(res.customers || []);
      } catch (err) {
        console.error('Failed to fetch customers:', err);
      } finally {
        setLoading(false);
      }
    }
    loadCust();
  }, []);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
          Customer Directory 360
          <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
            {customers.length} Accounts
          </span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">Customer profiles, lifetime values, payment histories, and recovery tracking</p>
      </div>

      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-xs font-mono">Loading customer records...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-3.5 pl-3">Customer ID</th>
                  <th className="py-3.5">Name</th>
                  <th className="py-3.5">Email</th>
                  <th className="py-3.5">Lifetime Value</th>
                  <th className="py-3.5">Successful Payments</th>
                  <th className="py-3.5">Failed Payments</th>
                  <th className="py-3.5">Recovered Revenue</th>
                  <th className="py-3.5 pr-3">Opted Out</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/customers/${c.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 pl-3 font-mono text-purple-700 font-bold">{c.external_customer_id}</td>
                    <td className="py-3.5 font-bold text-slate-900">{c.name}</td>
                    <td className="py-3.5 font-mono text-slate-600">{c.email}</td>
                    <td className="py-3.5 font-mono font-bold text-emerald-600">${c.lifetime_value?.toLocaleString()}</td>
                    <td className="py-3.5 font-mono text-slate-900">{c.successful_payments}</td>
                    <td className="py-3.5 font-mono text-rose-600 font-bold">{c.failed_payments}</td>
                    <td className="py-3.5 font-mono text-purple-700 font-bold">${c.recovered_revenue?.toLocaleString()}</td>
                    <td className="py-3.5 pr-3"><StatusBadge status={c.opted_out ? 'TRUE' : 'FALSE'} type="boolean" /></td>
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
