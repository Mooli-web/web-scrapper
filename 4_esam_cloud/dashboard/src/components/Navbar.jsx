import React, { useState, useEffect } from 'react';
import { ShoppingBag, Database, Radio, RefreshCw, Zap, Shield, HelpCircle, ExternalLink } from 'lucide-react';
import { testDbConnection } from '../api';

export default function Navbar({ onOpenDbModal, onOpenEsamModal }) {
  const [dbStatus, setDbStatus] = useState({ connected: false, latency: null, loading: false });

  const checkDb = async () => {
    setDbStatus((prev) => ({ ...prev, loading: true }));
    try {
      const res = await testDbConnection();
      setDbStatus({
        connected: res.connected || false,
        latency: res.latency_ms || 0,
        loading: false
      });
    } catch {
      setDbStatus({ connected: false, latency: null, loading: false });
    }
  };

  useEffect(() => {
    checkDb();
    const interval = setInterval(checkDb, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        {/* Left Side: Logo and Title */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-orange-600 to-amber-500 text-white shadow-lg shadow-orange-500/20 ring-1 ring-orange-400/30">
            <ShoppingBag className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base text-white tracking-tight">سامانه هوش و مانیتورینگ ایسام</span>
              <span className="rounded-md bg-orange-500/10 px-2 py-0.5 text-[11px] font-bold text-orange-400 border border-orange-500/30">
                Esam Cloud Engine
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">پایش ۲۴ ساعته مزایدات، قیمت کف بازار و کالاهای استوک</p>
          </div>
        </div>

        {/* Right Side: Quick Tools & Diagnostics */}
        <div className="flex items-center gap-2.5">
          {/* CockroachDB Health Pill */}
          <button
            onClick={onOpenDbModal}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 border border-slate-800 hover:border-slate-700 transition"
          >
            <div className={`h-2.5 w-2.5 rounded-full ${dbStatus.connected ? 'bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse' : 'bg-rose-500'}`} />
            <Database className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-300">
              {dbStatus.connected ? `CockroachDB (${dbStatus.latency}ms)` : 'دیتابیس متصل نیست'}
            </span>
          </button>

          {/* Esam Live Probe Button */}
          <button
            onClick={onOpenEsamModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-orange-500/10 text-orange-400 border border-orange-500/30 hover:bg-orange-500/20 transition"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>تست پروب زنده ایسام</span>
          </button>

          {/* Direct Link to Esam */}
          <a
            href="https://esam.ir"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 text-slate-400 border border-slate-800 hover:text-white hover:border-slate-700 transition"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>وب‌سایت ایسام</span>
          </a>
        </div>
      </div>
    </header>
  );
}
