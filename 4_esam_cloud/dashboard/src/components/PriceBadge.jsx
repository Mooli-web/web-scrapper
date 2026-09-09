import React from 'react';

export default function PriceBadge({ price, isAuction = false, bidsCount = 0, className = '' }) {
  if (!price || price === 0) {
    return <span className={`text-slate-400 text-xs ${className}`}>توافقی / نامشخص</span>;
  }

  const formatted = Number(price).toLocaleString('fa-IR');

  return (
    <div className={`inline-flex flex-col items-start ${className}`}>
      <div className="inline-flex items-baseline gap-1">
        <span className="font-extrabold text-orange-400 text-base">{formatted}</span>
        <span className="text-[11px] text-slate-400 font-medium">تومان</span>
      </div>
      {isAuction && bidsCount > 0 && (
        <span className="text-[10px] text-amber-400 font-semibold">
          ({Number(bidsCount).toLocaleString('fa-IR')} پیشنهاد ثبت‌شده)
        </span>
      )}
    </div>
  );
}
