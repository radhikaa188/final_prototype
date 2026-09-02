import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Bell,
  Search,
  ShieldCheck,
  ChevronRight,
  LogOut,
  Shield,
  Cpu,
  UserCheck,
  CreditCard,
  User,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
  X,
  Check,
  Loader2
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { api } from '../../api/client';

export const Header: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, role, logout } = useAuth();

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<{
    payments: any[];
    customers: any[];
    recovery_cases: any[];
    total_results: number;
  } | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // Notification state
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [notifLoading, setNotifLoading] = useState(false);
  const notifContainerRef = useRef<HTMLDivElement>(null);

  // 1. Keyboard shortcut Cmd+K / Ctrl+K for Global Search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
        setSearchOpen(true);
      } else if (e.key === 'Escape') {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 2. Click outside listeners for Search & Notifications
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
      if (notifContainerRef.current && !notifContainerRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 3. Debounced Search API query
  useEffect(() => {
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults(null);
      setIsSearching(false);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsSearching(true);
        const res = await api.search(query);
        setSearchResults(res);
        setSearchOpen(true);
      } catch (err) {
        console.error('Search query failed:', err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // 4. Fetch real notification telemetry
  const loadNotifications = async () => {
    try {
      setNotifLoading(true);
      const res = await api.getNotifications(20);
      setNotifications(res.notifications || []);
      setUnreadCount(res.unread_count || 0);
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setNotifLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 10000); // Polling every 10s
    return () => clearInterval(interval);
  }, []);

  // 5. Notification actions
  const handleNotificationClick = async (notif: any) => {
    try {
      if (!notif.is_read) {
        await api.markNotificationRead(notif.id);
        setNotifications(prev =>
          prev.map(n => (n.id === notif.id ? { ...n, is_read: true, clicked_at: new Date().toISOString() } : n))
        );
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
      setNotifOpen(false);

      if (notif.case_id) {
        navigate(`/recovery/${notif.case_id}`);
      } else if (notif.customer_id) {
        navigate(`/customers/${notif.customer_id}`);
      } else if (notif.type === 'HUMAN_REVIEW_REQUIRED') {
        navigate('/human-review');
      } else if (notif.type === 'CUSTOMER_ACTION_REQUIRED') {
        navigate('/customer-actions');
      }
    } catch (err) {
      console.error('Failed to mark notification read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true, clicked_at: new Date().toISOString() })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all read:', err);
    }
  };

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

  const formatTimeAgo = (dateStr?: string | null) => {
    if (!dateStr) return '';
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'RECOVERY_COMPLETED':
      case 'RETRY_SUCCESS':
      case 'CUSTOMER_ACTION_COMPLETED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
      case 'CUSTOMER_ACTION_REQUIRED':
      case 'CUSTOMER_NUDGE':
      case 'POLICY_BLOCKED':
        return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case 'HUMAN_REVIEW_REQUIRED':
      case 'HUMAN_APPROVED':
        return <Shield className="w-4 h-4 text-purple-600" />;
      case 'HUMAN_REJECTED':
      case 'RECOVERY_ATTEMPT_FAILED':
      case 'RECOVERY_STOPPED':
      case 'RECOVERY_WINDOW_EXPIRED':
        return <AlertTriangle className="w-4 h-4 text-rose-500" />;
      case 'RETRY_SCHEDULED':
      case 'AUTOMATIC_RETRY_ATTEMPTED':
        return <Clock className="w-4 h-4 text-blue-500" />;
      default:
        return <Activity className="w-4 h-4 text-slate-500" />;
    }
  };


  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between shrink-0 sticky top-0 z-30">
      {/* Breadcrumbs Navigation */}
      <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
        <span className="text-slate-400">Revora AI</span>
        <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
        <span className="text-slate-900 font-bold">{getPageTitle(location.pathname)}</span>
      </div>

      {/* Center Search & Right Action Cluster */}
      <div className="flex items-center gap-5">
        {/* Global Database-Backed Search Bar */}
        <div ref={searchContainerRef} className="relative w-80 hidden sm:block">
          <div className="relative">
            {isSearching ? (
              <Loader2 className="w-4 h-4 text-purple-600 absolute left-3 top-1/2 -translate-y-1/2 animate-spin" />
            ) : (
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            )}
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onFocus={() => {
                if (searchQuery.trim()) setSearchOpen(true);
              }}
              placeholder="Search payments, customers, cases..."
              className="w-full bg-[#F3F4F6] border border-slate-200 rounded-xl pl-9 pr-12 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-purple-500 focus:bg-white transition-all shadow-2xs"
            />
            {searchQuery ? (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSearchResults(null);
                  setSearchOpen(false);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            ) : (
              <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-slate-400 bg-white border border-slate-200 rounded shadow-2xs">
                ⌘K
              </kbd>
            )}
          </div>

          {/* Search Dropdown Results Popover */}
          {searchOpen && searchQuery.trim().length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden max-h-96 overflow-y-auto z-50 divide-y divide-slate-100">
              {isSearching && !searchResults && (
                <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-purple-600" />
                  Querying database records...
                </div>
              )}

              {searchResults && searchResults.total_results === 0 && (
                <div className="p-6 text-center text-xs text-slate-500">
                  No matching payments, customers, or cases found for &quot;<span className="font-semibold text-slate-700">{searchQuery}</span>&quot;.
                </div>
              )}

              {searchResults && searchResults.recovery_cases.length > 0 && (
                <div className="p-2">
                  <div className="text-[10px] font-bold text-slate-400 uppercase px-2 py-1 tracking-wider">
                    Recovery Cases ({searchResults.recovery_cases.length})
                  </div>
                  {searchResults.recovery_cases.map(caseItem => (
                    <button
                      key={caseItem.id}
                      onClick={() => {
                        navigate(`/recovery/${caseItem.id}`);
                        setSearchOpen(false);
                        setSearchQuery('');
                      }}
                      className="w-full text-left p-2 rounded-lg hover:bg-purple-50 transition flex items-center justify-between group cursor-pointer"
                    >
                      <div className="flex items-center gap-2.5">
                        <Activity className="w-4 h-4 text-purple-600 shrink-0" />
                        <div>
                          <div className="text-xs font-bold text-slate-900 group-hover:text-purple-700 font-mono">
                            {caseItem.id.substring(0, 16)}...
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {caseItem.customer_name} · ${caseItem.revenue_at_risk} · {caseItem.root_cause || 'Root Cause'}
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 group-hover:bg-purple-100 group-hover:text-purple-800">
                        {caseItem.status}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {searchResults && searchResults.payments.length > 0 && (
                <div className="p-2">
                  <div className="text-[10px] font-bold text-slate-400 uppercase px-2 py-1 tracking-wider">
                    Payments ({searchResults.payments.length})
                  </div>
                  {searchResults.payments.map(pay => (
                    <button
                      key={pay.id}
                      onClick={() => {
                        if (pay.recovery_case_id) {
                          navigate(`/recovery/${pay.recovery_case_id}`);
                        } else {
                          navigate('/payments');
                        }
                        setSearchOpen(false);
                        setSearchQuery('');
                      }}
                      className="w-full text-left p-2 rounded-lg hover:bg-slate-50 transition flex items-center justify-between group cursor-pointer"
                    >
                      <div className="flex items-center gap-2.5">
                        <CreditCard className="w-4 h-4 text-slate-500 shrink-0" />
                        <div>
                          <div className="text-xs font-bold text-slate-900 group-hover:text-slate-800 font-mono">
                            {pay.gateway_payment_id || pay.id}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            ${pay.amount} · {pay.failure_reason || pay.status} · {pay.customer_name}
                          </div>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                          pay.status === 'SUCCESS'
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-rose-50 text-rose-700'
                        }`}
                      >
                        {pay.status}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {searchResults && searchResults.customers.length > 0 && (
                <div className="p-2">
                  <div className="text-[10px] font-bold text-slate-400 uppercase px-2 py-1 tracking-wider">
                    Customers ({searchResults.customers.length})
                  </div>
                  {searchResults.customers.map(cust => (
                    <button
                      key={cust.id}
                      onClick={() => {
                        navigate(`/customers/${cust.id}`);
                        setSearchOpen(false);
                        setSearchQuery('');
                      }}
                      className="w-full text-left p-2 rounded-lg hover:bg-slate-50 transition flex items-center justify-between group cursor-pointer"
                    >
                      <div className="flex items-center gap-2.5">
                        <User className="w-4 h-4 text-blue-500 shrink-0" />
                        <div>
                          <div className="text-xs font-bold text-slate-900 group-hover:text-blue-600">
                            {cust.name}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {cust.email || cust.external_customer_id} · LTV: ${cust.lifetime_value}
                          </div>
                        </div>
                      </div>
                      <ExternalLink className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-600" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Action Cluster */}
        <div className="flex items-center gap-3">
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-[#F0FDF4] border border-emerald-200 text-[#16A34A] text-xs font-bold">
            <span className="w-2 h-2 rounded-full bg-[#16A34A] animate-pulse"></span>
            <ShieldCheck className="w-3.5 h-3.5" />
            Guardrails Active
          </div>

          {/* Database-Backed Notification Popover Control */}
          <div ref={notifContainerRef} className="relative">
            <button
              onClick={() => {
                setNotifOpen(!notifOpen);
                if (!notifOpen) loadNotifications();
              }}
              className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-900 transition-colors relative cursor-pointer"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-rose-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center border-2 border-white shadow-xs">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {/* Notification Dropdown Panel */}
            {notifOpen && (
              <div className="absolute right-0 mt-2 w-88 bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden z-50 divide-y divide-slate-100 animate-in fade-in zoom-in-95 duration-150">
                <div className="p-3.5 bg-slate-50 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">Notifications</span>
                    {unreadCount > 0 && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                        {unreadCount} unread
                      </span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={handleMarkAllRead}
                      className="text-[11px] text-purple-600 hover:text-purple-800 font-semibold flex items-center gap-1 cursor-pointer"
                    >
                      <Check className="w-3 h-3" />
                      Mark all as read
                    </button>
                  )}
                </div>

                <div className="max-h-96 overflow-y-auto divide-y divide-slate-50">
                  {notifLoading && notifications.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-purple-600" />
                      Loading notifications...
                    </div>
                  ) : notifications.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-400">
                      No notifications recorded yet.
                    </div>
                  ) : (
                    notifications.map(n => (
                      <button
                        key={n.id}
                        onClick={() => handleNotificationClick(n)}
                        className={`w-full text-left p-3.5 hover:bg-slate-50 transition flex gap-3 items-start cursor-pointer ${
                          !n.is_read ? 'bg-purple-50/40' : ''
                        }`}
                      >
                        <div className="p-2 rounded-lg bg-white border border-slate-200 shadow-2xs shrink-0 mt-0.5">
                          {getNotificationIcon(n.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-xs font-bold text-slate-900 truncate">
                              {n.type.replace(/_/g, ' ')}
                            </span>
                            <span className="text-[10px] text-slate-400 shrink-0 font-mono">
                              {formatTimeAgo(n.sent_at)}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-600 mt-0.5 line-clamp-2">
                            {n.recipient ? `Dispatched to ${n.recipient}` : 'Operational alert processed'}
                            {n.customer_name && n.customer_name !== 'System User' ? ` for ${n.customer_name}` : ''}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-bold">
                              {n.channel || 'IN_APP'}
                            </span>
                            {n.case_id && (
                              <span className="text-[9px] font-mono text-purple-600 font-bold">
                                Case: {n.case_id.substring(0, 8)}...
                              </span>
                            )}
                          </div>
                        </div>
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-purple-600 shrink-0 mt-1.5"></span>
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

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
              <div className="text-[10px] text-slate-400 mt-0.5 truncate max-w-[140px]">{user?.email || 'operator@revora.ai'}</div>
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

export default Header;
