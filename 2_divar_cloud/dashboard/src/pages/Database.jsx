import React, { useState } from 'react';
import { Database, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { wipeDatabase } from '../api';

export default function DatabaseView() {
  const [wiping, setWiping] = useState(false);
  const [result, setResult] = useState(null);

  const handleWipe = async () => {
    if (!window.confirm('آیا از پاکسازی کامل تمامی آگهی‌ها و داده‌های دیوار در دیتابیس اطمینان دارید؟')) return;
    setWiping(true);
    try {
      const res = await wipeDatabase();
      setResult({ success: true, message: res.message });
    } catch (e) {
      setResult({ success: false, message: String(e) });
    } finally {
      setWiping(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white">مدیریت دیتابیس اختصاصی دیوار (CockroachDB)</h2>
            <p className="text-xs text-slate-400">پایش مصرف فضا و ابزارهای نگهداری پایگاه داده ابری دیوار</p>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-rose-950/20 border border-rose-500/30 space-y-3">
          <div className="flex items-center gap-2 text-rose-400 text-xs font-bold">
            <AlertTriangle className="w-4 h-4" />
            <span>پاکسازی کامل دیتابیس دیوار (Database Wipe)</span>
          </div>
          <p className="text-xs text-slate-300">با زدن این دکمه، تمامی آگهی‌های ثبت‌شده دیوار صفر شده و دیتابیس پاکسازی می‌شود.</p>
          <button
            onClick={handleWipe}
            disabled={wiping}
            className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
          >
            <Trash2 className="w-4 h-4" />
            <span>{wiping ? 'در حال پاکسازی...' : 'پاکسازی تمام آگهی‌های دیتابیس'}</span>
          </button>
          {result && (
            <p className={`text-xs ${result.success ? 'text-emerald-400' : 'text-rose-400'}`}>
              {result.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
