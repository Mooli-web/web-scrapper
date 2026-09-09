import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'rose', trend }) {
  const colorMap = {
    rose: 'from-rose-500/20 to-rose-500/5 text-rose-400 border-rose-500/30',
    sky: 'from-sky-500/20 to-sky-500/5 text-sky-400 border-sky-500/30',
    emerald: 'from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/30',
    amber: 'from-amber-500/20 to-amber-500/5 text-amber-400 border-amber-500/30',
    purple: 'from-purple-500/20 to-purple-500/5 text-purple-400 border-purple-500/30',
  };

  const badgeColor = colorMap[color] || colorMap.rose;

  return (
    <div className="glass-card rounded-2xl p-5 relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-400 mb-1.5">{title}</p>
          <h3 className="text-2xl font-black text-white tracking-tight">{value}</h3>
          {subtitle && <p className="text-[11px] text-slate-400 mt-1">{subtitle}</p>}
        </div>
        {Icon && (
          <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${badgeColor} border flex items-center justify-center shrink-0`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      {trend && (
        <div className="mt-3.5 pt-3 border-t border-slate-800/80 flex items-center gap-1.5 text-xs">
          <span className={trend.positive ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
            {trend.text}
          </span>
          <span className="text-slate-400 text-[11px]">{trend.label}</span>
        </div>
      )}
    </div>
  );
}
