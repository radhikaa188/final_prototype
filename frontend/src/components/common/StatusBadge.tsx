import React from 'react';

interface StatusBadgeProps {
  status: string;
  type?: 'default' | 'action' | 'actor' | 'boolean';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalized = String(status || '').toUpperCase();

  let colorClasses = 'bg-slate-100 text-slate-700 border-slate-200';

  if (normalized === 'SUCCESS' || normalized === 'RECOVERED' || normalized === 'ALLOWED' || normalized === 'COMPLETED' || normalized === 'TRUE') {
    colorClasses = 'bg-[#F0FDF4] text-[#16A34A] border-emerald-200';
  } else if (normalized === 'FAILED' || normalized === 'BLOCKED' || normalized === 'STOPPED' || normalized === 'FALSE') {
    colorClasses = 'bg-[#FEF2F2] text-[#DC2626] border-rose-200';
  } else if (normalized === 'OPEN' || normalized === 'PRIORITIZED' || normalized === 'ACTION_PROPOSED' || normalized === 'AWAITING_APPROVAL') {
    colorClasses = 'bg-[#FFFBEB] text-[#D97706] border-amber-200';
  } else if (normalized === 'EXECUTING' || normalized === 'RUNNING' || normalized === 'APPROVED') {
    colorClasses = 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse';
  } else if (normalized === 'ESCALATED' || normalized === 'HUMAN_REVIEW' || normalized === 'NEEDS_REVIEW') {
    colorClasses = 'bg-[#F3E8FF] text-[#9333EA] border-purple-200';
  } else if (normalized === 'RETRY' || normalized === 'CUSTOMER_NUDGE') {
    colorClasses = 'bg-indigo-50 text-indigo-700 border-indigo-200';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${colorClasses}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
      {normalized}
    </span>
  );
};
