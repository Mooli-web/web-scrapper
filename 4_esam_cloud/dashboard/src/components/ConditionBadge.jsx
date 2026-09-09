import React from 'react';
import { Sparkles, ShieldCheck, Cpu, RefreshCw, AlertOctagon } from 'lucide-react';

export default function ConditionBadge({ condition }) {
  const cond = condition || 'دست دوم';

  if (cond.includes('پلمپ') || cond.includes('آکبند') || cond === 'نو') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        <Sparkles className="w-3 h-3 text-emerald-400" />
        نو (پلمپ)
      </span>
    );
  }

  if (cond.includes('در حد نو')) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-teal-500/10 text-teal-300 border border-teal-500/30">
        <ShieldCheck className="w-3 h-3 text-teal-400" />
        در حد نو
      </span>
    );
  }

  if (cond.includes('استوک')) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-sky-500/10 text-sky-300 border border-sky-500/30">
        <Cpu className="w-3 h-3 text-sky-400" />
        استوک گرید A
      </span>
    );
  }

  if (cond.includes('معیوب') || cond.includes('قطعات')) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
        <AlertOctagon className="w-3 h-3 text-rose-400" />
        معیوب / قطعات
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
      <RefreshCw className="w-3 h-3 text-amber-400" />
      دست دوم
    </span>
  );
}
