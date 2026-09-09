import React from 'react';
import { formatToman, formatPercent } from '../api';

export default function PriceBadge({ sellingPrice, rrpPrice, discountPercent, available = true }) {
  if (!available) {
    return (
      <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
        ناموجود
      </span>
    );
  }

  const hasDiscount = discountPercent && discountPercent > 0;

  return (
    <div className="flex flex-col items-end">
      <div className="flex items-center gap-1.5">
        <span className="font-bold text-white text-sm">{formatToman(sellingPrice)}</span>
        {hasDiscount && (
          <span className="px-1.5 py-0.5 rounded-md bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-black">
            {formatPercent(discountPercent)}
          </span>
        )}
      </div>
      {hasDiscount && rrpPrice > sellingPrice && (
        <span className="text-[11px] text-slate-400 line-through">
          {formatToman(rrpPrice)}
        </span>
      )}
    </div>
  );
}
