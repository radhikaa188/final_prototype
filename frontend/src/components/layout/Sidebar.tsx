import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  RefreshCw,
  Bot,
  UserCheck,
  Users,
  CreditCard,
  BarChart3,
  ShieldCheck,
  FileCheck2,
  PlugZap,
  Zap,
  FlaskConical
} from 'lucide-react';

const mainNav = [
  { path: '/dashboard', label: 'Command Center', icon: LayoutDashboard },
  { path: '/recovery', label: 'Recovery Queue', icon: RefreshCw },
  { path: '/customer-actions', label: 'Customer Actions', icon: UserCheck },
  { path: '/agent', label: 'Agent Operations', icon: Bot },
  { path: '/human-review', label: 'Human Review', icon: UserCheck },
];

const opsNav = [
  { path: '/customers', label: 'Customers', icon: Users },
  { path: '/payments', label: 'Payments', icon: CreditCard },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
];

const sysNav = [
  { path: '/audit', label: 'Audit Trail', icon: FileCheck2 },
  { path: '/policies', label: 'Policies & Guardrails', icon: ShieldCheck },
  { path: '/integrations', label: 'Integrations', icon: PlugZap },
  { path: '/test-mode', label: 'Test Mode Simulator', icon: FlaskConical },
];

export const Sidebar: React.FC = () => {
  const renderNavGroup = (title: string, items: typeof mainNav) => (
    <div className="space-y-1">
      <div className="px-3.5 pt-3 pb-1 text-[10px] font-bold font-mono tracking-wider text-slate-500 uppercase select-none">
        {title}
      </div>
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs transition-all duration-150 ${isActive
                ? 'bg-[#1E1E24] text-white font-bold shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#16161D]'
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0 text-slate-400" />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </div>
  );

  return (
    <aside className="w-64 bg-[#0D0D12] border-r border-[#1E1E24] flex flex-col justify-between shrink-0 min-h-screen">
      <div>
        {/* Brand Header */}
        <div className="p-6 border-b border-[#1E1E24] flex items-center gap-3">
          <div className="p-2 rounded-xl bg-purple-600 text-white shadow-md shadow-purple-600/30">
            <Zap className="w-5 h-5 fill-current" />
          </div>
          <div>
            <h1 className="text-base font-extrabold text-white tracking-wider">
              Recover<span className="text-purple-400">AI</span>
            </h1>
            <p className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
              Autonomous Recovery
            </p>
          </div>
        </div>

        {/* Navigation Groups */}
        <nav className="p-4 space-y-4">
          {renderNavGroup('Main Menu', mainNav)}
          {renderNavGroup('Operations', opsNav)}
          {renderNavGroup('System', sysNav)}
        </nav>
      </div>

      {/* Footer Info Card */}
      <div className="p-4 m-4 rounded-xl bg-[#16161D] border border-[#262630] text-xs text-slate-300">
        <div className="flex items-center gap-2 mb-1 text-slate-100 font-semibold">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          Engine Active
        </div>
        <p className="text-[11px] text-slate-400 font-mono">v1.0.0 • Telemetry ML v2.0</p>
      </div>
    </aside>
  );
};
