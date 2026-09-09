import React from 'react';
import { Gavel, Clock, Flame } from 'lucide-react';

export default function AuctionBadge({ isAuction, timeRemaining, bidsCount = 0 }) {
  if (!isAuction) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
        قیمت ثابت
      </span>
    );
  }

  const isHot = bidsCount >= 5;

  return (
    <div className="inline-flex flex-wrap items-center gap-1.5">
      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
        isHot 
          ? 'bg-gradient-to-r from-orange-500/20 to-rose-500/20 text-orange-400 border border-orange-500/40 animate-pulse'
          : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
      }`}>
        {isHot ? <Flame className="w-3 h-3 text-orange-400 animate-bounce" /> : <Gavel className="w-3 h-3 text-amber-400" />}
        مزایده ایسام
      </span>

      {timeRemaining && (
        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800" dir="ltr">
          <Clock className="w-3 h-3 text-slate-500" />
          {timeRemaining}
        </span>
      )}
    </div>
  );
}
