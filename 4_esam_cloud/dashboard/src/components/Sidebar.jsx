import React from 'react';
import { LayoutDashboard, ShoppingBag, Gavel, TrendingDown, Layers, Database, Activity } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'نمای کلی و آمار', icon: LayoutDashboard },
  { id: 'items', label: 'دفتر کل کالاها و استوک', icon: ShoppingBag },
  { id: 'auctions', label: 'مزایدات داغ و رو به پایان', icon: Gavel, badge: 'زنده' },
  { id: 'events', label: 'نوسانات قیمت و پیشنهادها', icon: TrendingDown },
  { id: 'categories', label: 'دسته‌بندی‌های هدف', icon: Layers },
  { id: 'database', label: 'وضعیت CockroachDB', icon: Database },
];

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="w-64 flex-shrink-0 border-l border-slate-800 bg-slate-950/60 p-4 flex flex-col justify-between">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-bold tracking-wider text-slate-500 uppercase">
          ماژول‌های اختصاصی ایسام
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-orange-500/20 to-amber-500/10 text-orange-400 border border-orange-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-orange-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="px-1.5 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Engine Status footer */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-xs">
        <div className="flex items-center gap-2 text-slate-300 font-semibold mb-1">
          <Activity className="w-3.5 h-3.5 text-orange-400" />
          <span>موتور ایسام (Esam Engine)</span>
        </div>
        <p className="text-[11px] text-slate-400">
          معماری مستقل و بدون وابستگی روی سرور ابری Render
        </p>
      </div>
    </aside>
  );
}
