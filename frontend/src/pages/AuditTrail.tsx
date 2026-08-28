import React, { useEffect, useState } from 'react';
import { Filter, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../api/client';
import { StatusBadge } from '../components/common/StatusBadge';

export const AuditTrail: React.FC = () => {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actorFilter, setActorFilter] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchAuditEvents = async () => {
    try {
      setLoading(true);
      const res = await api.getAuditEvents(actorFilter);
      setEvents(res.events || []);
    } catch (err) {
      console.error('Failed to load audit trail:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditEvents();
  }, [actorFilter]);

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            Immutable Audit Trail Log
            <span className="text-xs px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 font-mono border border-purple-200 font-bold">
              {events.length} Recorded Events
            </span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">Audit log of system, ML, agent decisions, policy evaluations, and payment executions</p>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer font-medium"
          >
            <option value="">All Actors</option>
            <option value="SYSTEM">SYSTEM</option>
            <option value="ML">ML</option>
            <option value="AGENT">AGENT</option>
            <option value="POLICY_ENGINE">POLICY_ENGINE</option>
            <option value="EXECUTOR">EXECUTOR</option>
            <option value="HUMAN">HUMAN</option>
            <option value="GATEWAY">GATEWAY</option>
          </select>
        </div>
      </div>

      <div className="glass-panel p-6 rounded-xl border border-slate-200 bg-white space-y-4">
        {loading ? (
          <div className="p-8 text-center text-slate-500 text-xs font-mono">Loading audit events...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase tracking-wider font-mono border-b border-slate-200 text-[10px] bg-slate-50">
                <tr>
                  <th className="py-3.5 pl-3">Timestamp</th>
                  <th className="py-3.5">Actor</th>
                  <th className="py-3.5">Event Type</th>
                  <th className="py-3.5">Case ID</th>
                  <th className="py-3.5 pr-3">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {events.map((ev) => (
                  <React.Fragment key={ev.id}>
                    <tr
                      onClick={() => setExpandedId(expandedId === ev.id ? null : ev.id)}
                      className="hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 pl-3 font-mono text-slate-500 text-[11px]">
                        {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : 'N/A'}
                      </td>
                      <td className="py-3.5"><StatusBadge status={ev.actor_type} /></td>
                      <td className="py-3.5 font-mono font-bold text-purple-700">{ev.event_type}</td>
                      <td className="py-3.5 font-mono text-slate-500">{ev.case_id ? `${ev.case_id.substring(0, 8)}...` : 'System Wide'}</td>
                      <td className="py-3.5 pr-3 text-slate-800 flex items-center justify-between font-medium">
                        <span>{ev.description}</span>
                        {expandedId === ev.id ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                      </td>
                    </tr>
                    {expandedId === ev.id && ev.metadata && (
                      <tr>
                        <td colSpan={5} className="p-4 bg-slate-900 text-slate-100 font-mono text-[11px]">
                          <div className="font-bold text-purple-400 mb-1">RAW AUDIT METADATA PAYLOAD:</div>
                          <pre className="overflow-x-auto text-purple-300">{JSON.stringify(ev.metadata, null, 2)}</pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
