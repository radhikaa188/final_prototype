import React from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, Search, ShieldCheck, Moon, ChevronRight } from 'lucide-react';

export const Header: React.FC = () => {
  const location = useLocation();

  const getPageTitle = (path: string) => {
    if (path === '/') return 'Command Center';
    if (path.startsWith('/recovery')) return 'Recovery Queue';
    if (path.startsWith('/agent')) return 'Agent Operations';
    if (path.startsWith('/human-review')) return 'Human Review';
    if (path.startsWith('/customers')) return 'Customers';
    if (path.startsWith('/payments')) return 'Payments';
    if (path.startsWith('/analytics')) return 'Analytics';
    if (path.startsWith('/audit')) return 'Audit Trail';
    if (path.startsWith('/policies')) return 'Policies & Guardrails';
    if (path.startsWith('/integrations')) return 'Integrations';
    if (path.startsWith('/test-mode')) return 'Test Mode Simulator';
    return 'Dashboard';
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between shrink-0">
      {/* Breadcrumbs Navigation */}
      <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
        <span className="text-slate-400">RecoverAI</span>
        <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
        <span className="text-slate-900 font-bold">{getPageTitle(location.pathname)}</span>
      </div>

      {/* Search Input with Shortcut Pill */}
      <div className="flex items-center gap-6">
        <div className="relative w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search payments, customers..."
            className="w-full bg-[#F3F4F6] border border-slate-200 rounded-[8px] pl-9 pr-12 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-purple-500 focus:bg-white transition-all"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-slate-400 bg-white border border-slate-200 rounded shadow-2xs">
            ⌘K
          </kbd>
        </div>

        {/* Status Pill & Right Action Cluster */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#F0FDF4] border border-emerald-200 text-[#16A34A] text-xs font-bold">
            <span className="w-2 h-2 rounded-full bg-[#16A34A] animate-pulse"></span>
            <ShieldCheck className="w-3.5 h-3.5" />
            Guardrails Active
          </div>

          <button className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-900 transition-colors relative cursor-pointer">
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-rose-500"></span>
          </button>

          <button className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-900 transition-colors cursor-pointer">
            <Moon className="w-4 h-4" />
          </button>

          {/* User Profile Avatar */}
          <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
            <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center font-bold text-white text-xs shadow-sm">
              OP
            </div>
            <div className="hidden md:block">
              <div className="text-xs font-bold text-slate-900 leading-none">Ops Command</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Operations Lead</div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
