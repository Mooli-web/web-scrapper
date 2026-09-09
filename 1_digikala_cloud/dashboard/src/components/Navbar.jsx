import React, { useState } from 'react';
import { Activity, RefreshCw, Database, Globe, LogOut, UserCheck } from 'lucide-react';
import DbTestModal from './DbTestModal';
import DigikalaTestModal from './DigikalaTestModal';
import { logout } from '../api';

export default function Navbar({ onRefresh, isRefreshing, currentUser }) {
  const [isDbModalOpen, setIsDbModalOpen] = useState(false);
  const [isDigiModalOpen, setIsDigiModalOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-rose-600 to-rose-400 flex items-center justify-center shadow-lg shadow-rose-500/20">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white tracking-tight">سامانه هوش بازار دیجیتال</h1>
              <span className="px-2 py-0.5 text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-full">
                Digikala Cloud
              </span>
            </div>
            <p className="text-xs text-slate-400">پایش ۲۴ ساعته دیجی‌کالا، کشف تخفیف فیک و ردیابی جنگ قیمت فروشندگان</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {currentUser && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs">
              <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-bold text-white">{currentUser.username}</span>
            </div>
          )}

          <button
            onClick={() => setIsDbModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 transition cursor-pointer"
            title="سنجش اتصال CockroachDB"
          >
            <Database className="w-3.5 h-3.5 text-sky-400" />
            <span>تست دیتابیس</span>
          </button>

          <button
            onClick={() => setIsDigiModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 transition cursor-pointer"
            title="سنجش API دیجی‌کالا"
          >
            <Globe className="w-3.5 h-3.5 text-rose-400" />
            <span>تست دیجی‌کالا</span>
          </button>

          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-md shadow-rose-600/20 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>بروزرسانی</span>
          </button>

          {currentUser && (
            <button
              onClick={logout}
              title="خروج از حساب"
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-600/20 text-slate-400 hover:text-rose-400 border border-slate-700 transition cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </header>

      <DbTestModal isOpen={isDbModalOpen} onClose={() => setIsDbModalOpen(false)} />
      <DigikalaTestModal isOpen={isDigiModalOpen} onClose={() => setIsDigiModalOpen(false)} />
    </>
  );
}
