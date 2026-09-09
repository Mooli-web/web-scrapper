import React, { useState } from 'react';
import { X, Database, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { testDbConnection } from '../api';

export default function DbTestModal({ isOpen, onClose }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleTest = async () => {
    setLoading(true);
    try {
      const data = await testDbConnection();
      setResult(data);
    } catch (e) {
      setResult({ status: 'error', connected: false, error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <Database className="w-5 h-5 text-orange-400" />
            <h3 className="text-base font-bold text-white">تست اتصال دیتابیس CockroachDB ایسام</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="py-5 space-y-4">
          <p className="text-xs text-slate-300 leading-relaxed">
            این ابزار سلامت اتصال سرور به دیتابیس مستقل ایسام و تعداد رکوردهای ثبت‌شده در جداول را بررسی می‌کند.
          </p>

          <button
            onClick={handleTest}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-bold transition disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
            <span>اجرای تست زنده دیتابیس</span>
          </button>

          {result && (
            <div className={`p-4 rounded-xl border ${result.connected ? 'bg-emerald-950/40 border-emerald-500/30' : 'bg-rose-950/40 border-rose-500/30'}`}>
              <div className="flex items-center gap-2 mb-2 font-bold text-sm">
                {result.connected ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-emerald-400">اتصال برقرار است (پینگ: {result.latency_ms}ms)</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    <span className="text-rose-400">خطا در اتصال به CockroachDB</span>
                  </>
                )}
              </div>

              {result.error && (
                <p className="text-xs text-rose-300 font-mono mt-1 break-words">{result.error}</p>
              )}

              {result.table_counts && (
                <div className="mt-3 pt-3 border-t border-slate-800 grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 rounded bg-slate-900/80">
                    <span className="text-slate-400">کالاهای ثبت‌شده:</span>{' '}
                    <span className="font-bold text-white">{result.table_counts.esam_items || 0}</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900/80">
                    <span className="text-slate-400">تاریخچه قیمت‌ها:</span>{' '}
                    <span className="font-bold text-white">{result.table_counts.esam_price_observations || 0}</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900/80">
                    <span className="text-slate-400">رویدادهای نوسان:</span>{' '}
                    <span className="font-bold text-white">{result.table_counts.esam_price_events || 0}</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900/80">
                    <span className="text-slate-400">دسته‌بندی‌ها:</span>{' '}
                    <span className="font-bold text-white">{result.table_counts.esam_categories || 0}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end pt-3 border-t border-slate-800">
          <button onClick={onClose} className="px-4 py-1.5 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700">
            بستن
          </button>
        </div>
      </div>
    </div>
  );
}
