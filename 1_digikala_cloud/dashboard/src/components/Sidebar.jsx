import React, { useState } from 'react';
import {
  LayoutDashboard,
  Layers,
  Package,
  Flame,
  Database,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Swords
} from 'lucide-react';

const MENU_ITEMS = [
  { id: 'overview', label: 'مرکز پایش زنده (Overview)', icon: LayoutDashboard },
  { id: 'fake-discounts', label: 'تشخیص تخفیف فیک (Fake Detector)', icon: ShieldAlert },
  { id: 'seller-war', label: 'جنگ قیمت و بای‌باکس (Seller War)', icon: Swords },
  { id: 'products', label: 'دفترکل و کاتالوگ کالاها (Products)', icon: Package },
  { id: 'categories', label: 'کاوشگر درختی دسته‌ها (Categories)', icon: Layers },
  { id: 'events', label: 'افت قیمت و هشدارها (Events)', icon: Flame },
  { id: 'database', label: 'مدیریت دیتابیس (Storage)', icon: Database },
  { id: 'status', label: 'عیب‌یابی و سلامت سیستم (Status)', icon: CheckCircle2 },
];

export default function Sidebar({ activeTab, onSelectTab }) {
  const [sidebarWidth, setSidebarWidth] = useState(270);
  const [isCompact, setIsCompact] = useState(false);

  return (
    <aside
      style={{ width: isCompact ? '75px' : `${sidebarWidth}px` }}
      className="relative bg-slate-900/85 backdrop-blur-md border-l border-slate-800 p-3.5 flex flex-col justify-between shrink-0 select-none min-h-[calc(100vh-61px)]"
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1 border-b border-slate-800/80 pb-2 text-slate-400">
          {!isCompact && (
            <span className="text-[11px] font-black tracking-wider uppercase text-slate-300">
              سامانه هوش دیجی‌کالا
            </span>
          )}
          <button
            onClick={() => setIsCompact(!isCompact)}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition cursor-pointer mx-auto"
          >
            {isCompact ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        <nav className="space-y-1">
          {MENU_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                title={isCompact ? item.label : undefined}
                className={`w-full flex items-center ${
                  isCompact ? 'justify-center px-2 py-3' : 'justify-start gap-3 px-3 py-2.5'
                } rounded-xl text-xs font-bold transition cursor-pointer text-right ${
                  isActive
                    ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30 shadow-sm shadow-rose-500/10'
                    : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-rose-400' : 'text-slate-400'}`} />
                {!isCompact && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>
      </div>

      {!isCompact && (
        <div className="pt-4 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
          <div className="flex items-center justify-between text-slate-300">
            <span>موتور دیجی‌کالا:</span>
            <span className="text-emerald-400 font-bold">۲۴/۷ پیوسته</span>
          </div>
          <div className="flex items-center justify-between text-slate-300">
            <span>دیتابیس:</span>
            <span className="text-sky-400 font-bold">CockroachDB</span>
          </div>
        </div>
      )}
    </aside>
  );
}
