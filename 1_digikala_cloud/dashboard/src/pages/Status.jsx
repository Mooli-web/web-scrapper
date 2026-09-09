import React, { useState, useEffect } from 'react';
import { CheckCircle2, Server, Database, Globe, Clock, RefreshCw } from 'lucide-react';
import { fetchStatus } from '../api';
import DbTestModal from '../components/DbTestModal';
import DigikalaTestModal from '../components/DigikalaTestModal';

export default function Status() {
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isDbModalOpen, setIsDbModalOpen] = useState(false);
  const [isDigiModalOpen, setIsDigiModalOpen] = useState(false);

  const loadStatus = async () => {
    setLoading(true);
    const data = await fetchStatus();
    setStatusData(data);
    setLoading(false);
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const dbHealth = statusData?.database || {};
  const isDbConnected = Boolean(dbHealth.connected);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-slate-900/90 via-slate-900/80 to-slate-950 border border-slate-700/60 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`w-11 h-11 rounded-2xl flex items-center justify-center border shadow-lg ${
            isDbConnected
              ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
              : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
          }`}>
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white">وضعیت سلامت و عیب‌یابی سرویس‌ها (System Diagnostics)</h2>
            <p className="text-xs text-slate-400">سنجش مستقیم تاخیر شبکه به CockroachDB و دسترسی به API دیجی‌کالا</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsDbModalOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-400 border border-slate-700 text-xs font-bold transition cursor-pointer flex items-center gap-1.5"
          >
            <Database className="w-4 h-4" />
            <span>تست دیتابیس</span>
          </button>

          <button
            onClick={() => setIsDigiModalOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-rose-400 border border-slate-700 text-xs font-bold transition cursor-pointer flex items-center gap-1.5"
          >
            <Globe className="w-4 h-4" />
            <span>تست دیجی‌کالا</span>
          </button>

          <button
            onClick={loadStatus}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white transition cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Service Diagnostic Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* CockroachDB Serverless */}
        <div className={`glass-card rounded-3xl p-6 border space-y-3 ${
          isDbConnected ? 'border-slate-800' : 'border-rose-500/40 bg-rose-950/10'
        }`}>
          <div className="flex items-center justify-between">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center border ${
              isDbConnected ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/20 border-rose-500/30 text-rose-400'
            }`}>
              <Database className="w-4 h-4" />
            </div>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
              isDbConnected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
            }`}>
              {isDbConnected ? 'متصل به CockroachDB' : 'عدم اتصال (قطع)'}
            </span>
          </div>

          <div>
            <h3 className="text-sm font-bold text-white">CockroachDB Cloud</h3>
            <p className="text-xs text-slate-400 mt-1">
              {isDbConnected 
                ? `پایگاه‌داده فعال: ${dbHealth.database_name || 'defaultdb'}` 
                : 'رشته اتصال DATABASE_URL نامعتبر یا تنظیم‌نشده است.'}
            </p>
          </div>

          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>تاخیر پینگ واقعی:</span>
              <span className="font-mono text-emerald-400 font-bold">
                {isDbConnected ? `${dbHealth.latency_ms} ms` : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>هاست متصل:</span>
              <span className="font-mono text-white text-[10px] truncate max-w-[160px]">
                {dbHealth.host || 'تنظیم‌نشده'}
              </span>
            </div>
          </div>
        </div>

        {/* Render Web Service */}
        <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="w-9 h-9 rounded-xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <Server className="w-4 h-4" />
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400">
              فعال و آنلاین
            </span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">سرور وب Render (داشبورد + API)</h3>
            <p className="text-xs text-slate-400 mt-1">سرویس FastAPI و بیلد ری‌اکت در دسترس است</p>
          </div>
          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>وب‌سوکت تلمتری:</span>
              <span className="text-emerald-400 font-mono font-bold">فعال (/ws/crawler-live)</span>
            </div>
          </div>
        </div>

        {/* Crawler Mode */}
        <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="w-9 h-9 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Clock className="w-4 h-4" />
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-400">
              پایش پیوسته ۲۴/۷
            </span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">ورکر پایش آرام و پیوسته</h3>
            <p className="text-xs text-slate-400 mt-1">۱ درخواست در هر ۱.۸ ثانیه برای امنیت و پایداری کامل</p>
          </div>
          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>وضعیت ورکر:</span>
              <span className="font-mono text-emerald-400 font-bold">
                {statusData?.crawler_telemetry?.status === 'running' ? 'در حال خزش' : 'آماده'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <DbTestModal isOpen={isDbModalOpen} onClose={() => setIsDbModalOpen(false)} />
      <DigikalaTestModal isOpen={isDigiModalOpen} onClose={() => setIsDigiModalOpen(false)} />
    </div>
  );
}
