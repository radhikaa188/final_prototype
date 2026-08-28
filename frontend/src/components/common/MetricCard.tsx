import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
  color?: 'cyan' | 'emerald' | 'amber' | 'purple' | 'rose';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendUp = true
}) => {
  return (
    <div className="glass-panel p-5 rounded-xl border border-slate-200 bg-white transition-all duration-200 hover:border-slate-300">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase font-mono">{title}</span>
        {icon && <div className="p-2 rounded-lg bg-slate-50 text-slate-600 border border-slate-200">{icon}</div>}
      </div>
      <div className="text-2xl font-black text-slate-900 font-mono tracking-tight">{value}</div>
      {(subtitle || trend) && (
        <div className="flex items-center justify-between text-xs text-slate-500 mt-3 pt-2.5 border-t border-slate-100">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span className={`font-bold ${trendUp ? 'text-emerald-600' : 'text-rose-600'}`}>
              {trendUp ? '↑' : '↓'} {trend}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
