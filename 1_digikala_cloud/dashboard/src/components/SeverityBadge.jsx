import React from 'react';
import { AlertCircle, Flame, Info } from 'lucide-react';

export default function SeverityBadge({ severity }) {
  const s = (severity || 'low').toLowerCase();

  if (s === 'high') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
        <Flame className="w-3 h-3 text-rose-400" />
        افت شدید
      </span>
    );
  }

  if (s === 'medium') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
        <AlertCircle className="w-3 h-3 text-amber-400" />
        افت متوسط
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-sky-500/15 text-sky-300 border border-sky-500/30">
      <Info className="w-3 h-3 text-sky-400" />
      عادی
    </span>
  );
}
