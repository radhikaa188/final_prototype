import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Search, ShieldCheck, ChevronRight, LogOut, Shield, Cpu, UserCheck } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

export const Header: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, role, logout } = useAuth();

  const getPageTitle = (path: string) => {
    if (path === '/' || path === '/dashboard') return 'Command Center';
    if (path.startsWith('/recovery')) return 'Recovery Queue';
    if (path.startsWith('/agent')) return 'Agent Operations';
    if (path.startsWith('/human-review')) return 'Human Review';
    if (path.startsWith('/customer-actions')) return 'Customer Actions';
    if (path.startsWith('/customers')) return 'Customers';
    if (path.startsWith('/payments')) return 'Payments';
    if (path.startsWith('/analytics')) return 'Analytics';
    if (path.startsWith('/audit')) return 'Audit Trail';
    if (path.startsWith('/policies')) return 'Policies & Guardrails';
    if (path.startsWith('/integrations')) return 'Integrations';
    if (path.startsWith('/test-mode')) return 'Test Mode Simulator';
    return 'Dashboard';
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getRoleBadge = () => {
    switch (role) {
      case 'ADMIN':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-200 text-[10px] font-bold">
            <Shield size={10} /> ADMIN
          </span>
        );
      case 'OPS':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold">
            <Cpu size={10} /> OPS
          </span>
        );
      case 'VIEWER':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
            <UserCheck size={10} /> VIEWER
          </span>
        );
      default:
        return null;
    }
  };

  const initials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()
    : (user?.email?.substring(0, 2).toUpperCase() || 'OP');

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between shrink-0">
      {/* Breadcrumbs Navigation */}
      <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
        <span className="text-slate-400">RecoverAI</span>
        <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
        <span className="text-slate-900 font-bold">{getPageTitle(location.pathname)}</span>
      </div>

      {/* Search Input with Shortcut Pill */}
      <div className="flex items-center gap-5">
        <div className="relative w-64 hidden sm:block">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search payments, customers..."
            className="w-full bg-[#F3F4F6] border border-slate-200 rounded-[8px] pl-9 pr-12 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-slate-400 bg-white border border-slate-200 rounded shadow-2xs">
            ⌘K
          </kbd>
        </div>

        {/* Status Pill & Right Action Cluster */}
        <div className="flex items-center gap-3">
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-[#F0FDF4] border border-emerald-200 text-[#16A34A] text-xs font-bold">
            <span className="w-2 h-2 rounded-full bg-[#16A34A] animate-pulse"></span>
            <ShieldCheck className="w-3.5 h-3.5" />
            Guardrails Active
          </div>

          <button className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-900 transition-colors relative cursor-pointer" title="Notifications">
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-rose-500"></span>
          </button>

          {/* User Profile Avatar & Role */}
          <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
            <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-white text-xs shadow-sm">
              {initials}
            </div>
            <div className="hidden md:block">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold text-slate-900 leading-none">{user?.name || user?.email || 'Operator'}</span>
                {getRoleBadge()}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5 truncate max-w-[140px]">{user?.email || 'operator@recoverai.io'}</div>
            </div>

            {/* Logout Button */}
            <button
              onClick={handleLogout}
              className="ml-2 p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition cursor-pointer"
              title="Sign Out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
