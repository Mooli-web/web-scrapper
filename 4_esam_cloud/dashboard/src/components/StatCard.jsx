import React from 'react';

export default function StatCard({ title, value, unit, icon: Icon, color = 'orange', subtext }) {
  const colorMap = {
    orange: 'from-orange-500/20 to-orange-500/5 text-orange-400 border-orange-500/30',
    amber: 'from-amber-500/20 to-amber-500/5 text-amber-400 border-amber-500/30',
    emerald: 'from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/30',
    sky: 'from-sky-500/20 to-sky-500/5 text-sky-400 border-sky-500/30',
    rose: 'from-rose-500/20 to-rose-500/5 text-rose-400 border-rose-500/30'
  };

  const selectedColor = colorMap[color] || colorMap.orange;

  return (
    <div className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${selectedColor} p-5 border shadow-lg backdrop-blur-sm`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-slate-400 mb-1">{title}</p>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-2xl font-black text-white tracking-tight">
              {typeof value === 'number' ? value.toLocaleString('fa-IR') : (value || '۰')}
            </span>
            {unit && <span className="text-xs font-medium text-slate-400">{unit}</span>}
          </div>
        </div>
        {Icon && (
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-700/50 shadow-inner">
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
      {subtext && (
        <div className="mt-3 pt-2.5 border-t border-slate-800/80 text-[11px] text-slate-400">
          {subtext}
        </div>
      )}
    </div>
  );
}
