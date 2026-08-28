import React, { useState } from 'react';
import { CheckCircle2, RefreshCw } from 'lucide-react';

export const Integrations: React.FC = () => {
  const [checking, setChecking] = useState(false);

  const handleHealthCheck = () => {
    setChecking(true);
    setTimeout(() => setChecking(false), 800);
  };

  const integrations = [
    { name: 'Simulated Payment Gateway', type: 'Gateway Connector', status: 'Connected', ping: '12ms', details: 'Handles simulated payment retries and billing webhooks.' },
    { name: 'FastAPI Backend Core', type: 'REST API & SSE', status: 'Connected', ping: '4ms', details: 'FastAPI service running on port 8000 with EventSource support.' },
    { name: 'Database Engine (SQLite/PostgreSQL)', type: 'Relational DB', status: 'Connected', ping: '2ms', details: 'Primary source of truth for payments, cases, policies & audit events.' },
    { name: 'Retrained Telemetry ML Service', type: 'Machine Learning', status: 'Online', ping: '8ms', details: 'LogisticRegression Model trained on payment_failure.csv telemetry.' },
    { name: 'Notification Service', type: 'Event Dispatcher', status: 'Active', ping: '5ms', details: 'Customer email nudges & operational review notifications.' },
  ];

  return (
    <div className="p-8 space-y-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            System Integrations &amp; Telemetry Health
          </h1>
          <p className="text-xs text-slate-500 mt-1">Live status of interconnected microservices, payment gateways, and databases</p>
        </div>
        <button
          onClick={handleHealthCheck}
          disabled={checking}
          className="btn-dark flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${checking ? 'animate-spin' : ''}`} />
          Run System Diagnostics
        </button>
      </div>

      <div className="space-y-4">
        {integrations.map((item, i) => (
          <div key={i} className="glass-panel p-6 rounded-xl border border-slate-200 bg-white flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-[#F0FDF4] text-[#16A34A] border border-emerald-200">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  {item.name}
                  <span className="text-[10px] font-mono text-slate-500 px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 font-bold">{item.type}</span>
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">{item.details}</p>
              </div>
            </div>

            <div className="text-right space-y-1">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#F0FDF4] text-[#16A34A] border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] animate-pulse"></span>
                {item.status}
              </span>
              <div className="text-[10px] font-mono text-slate-500">Latency: {item.ping}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
