import React, { useState, useEffect } from 'react';
import { Database, CheckCircle2, AlertTriangle, RefreshCw, Server, HardDrive, Shield } from 'lucide-react';
import { testDbConnection } from '../api';

export default function DatabasePage() {
  const [dbInfo, setDbInfo] = useState(null);
  const [loading, setLoading] = useState(false);

  const checkDb = async () => {
    setLoading(true);
    try {
      const data = await testDbConnection();
      setDbInfo(data);
    } catch (e) {
      setDbInfo({ connected: false, error: e.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkDb();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-white">پایگاه داده مستقل ایسام (CockroachDB Serverless)</h1>
          <p className="text-xs text-slate-400 mt-1">
            وضعیت کلاستر اختصاصی دیتابیس ایسام و آمار جداول ذخیره‌سازی مزایدات و کالاها
          </p>
        </div>

        <button
          onClick={checkDb}
          disabled={loading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>تست مجدد اتصال</span>
        </button>
      </div>

      {/* Connection Status Card */}
      <div className={`p-6 rounded-2xl border ${dbInfo?.connected ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-rose-950/20 border-rose-500/30'} backdrop-blur-sm`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-xl ${dbInfo?.connected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
              <Database className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">
                {dbInfo?.connected ? 'اتصال به CockroachDB Serverless برقرار است' : 'عدم اتصال به دیتابیس'}
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                موتور: {dbInfo?.engine || 'CockroachDB'} | دیتابیس: {dbInfo?.database_name || 'defaultdb'}
              </p>
            </div>
          </div>

          {dbInfo?.connected && (
            <div className="text-left">
              <span className="text-xs text-slate-400">تاخیر زمانی (Latency)</span>
              <p className="text-xl font-mono font-black text-emerald-400">{dbInfo.latency_ms} ms</p>
            </div>
          )}
        </div>

        {dbInfo?.error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-900/30 border border-rose-800 text-xs text-rose-300 font-mono">
            {dbInfo.error}
          </div>
        )}
      </div>

      {/* Tables Breakdown */}
      {dbInfo?.table_counts && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <h3 className="text-sm font-bold text-white mb-4">آمار رکوردهای جداول دیتابیس ایسام</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <p className="text-xs text-slate-400">جدول کالاهای ایسام (esam_items)</p>
              <p className="text-2xl font-black text-white mt-1 font-mono">
                {Number(dbInfo.table_counts.esam_items || 0).toLocaleString('fa-IR')}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <p className="text-xs text-slate-400">تاریخچه قیمت‌ها (esam_price_obs)</p>
              <p className="text-2xl font-black text-emerald-400 mt-1 font-mono">
                {Number(dbInfo.table_counts.esam_price_observations || 0).toLocaleString('fa-IR')}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <p className="text-xs text-slate-400">رویدادها و نوسانات (esam_events)</p>
              <p className="text-2xl font-black text-amber-400 mt-1 font-mono">
                {Number(dbInfo.table_counts.esam_price_events || 0).toLocaleString('fa-IR')}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
              <p className="text-xs text-slate-400">دسته‌بندی‌های هدف (esam_categories)</p>
              <p className="text-2xl font-black text-sky-400 mt-1 font-mono">
                {Number(dbInfo.table_counts.esam_categories || 0).toLocaleString('fa-IR')}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
