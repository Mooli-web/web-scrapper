import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertCircle, Database, Smartphone } from 'lucide-react';
import { testDbConnection, testDivarConnection } from '../api';

export default function Status() {
  const [dbStatus, setDbStatus] = useState(null);
  const [divarStatus, setDivarStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([testDbConnection(), testDivarConnection()]).then(([dbRes, divarRes]) => {
      setDbStatus(dbRes);
      setDivarStatus(divarRes);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-2">
        <h2 className="text-lg font-black text-white">وضعیت سلامت و عیب‌یابی سرویس‌های دیوار</h2>
        <p className="text-xs text-slate-400">سنجش مستقیم وضعیت اتصال سرور Render به CockroachDB و دیوار</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card rounded-2xl p-5 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-sky-400" />
            <span className="font-bold text-white text-sm">پایگاه‌داده CockroachDB دیوار</span>
          </div>
          {loading ? (
            <p className="text-xs text-slate-400">در حال ارزیابی...</p>
          ) : (
            <div className="text-xs space-y-1">
              <p>وضعیت: <span className={dbStatus?.connected ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{dbStatus?.status || 'نامشخص'}</span></p>
              <p>تاخیر پینگ: <span className="text-white font-mono">{dbStatus?.latency_ms || 0} ms</span></p>
              <p>دیتابیس: <span className="text-slate-300 font-mono">{dbStatus?.database_name || 'defaultdb'}</span></p>
            </div>
          )}
        </div>

        <div className="glass-card rounded-2xl p-5 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-amber-400" />
            <span className="font-bold text-white text-sm">وب‌سرویس دیوار (api.divar.ir)</span>
          </div>
          {loading ? (
            <p className="text-xs text-slate-400">در حال ارزیابی...</p>
          ) : (
            <div className="text-xs space-y-1">
              <p>وضعیت دسترسی: <span className={divarStatus?.reachable ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{divarStatus?.status || 'نامشخص'}</span></p>
              <p>تاخیر پینگ: <span className="text-white font-mono">{divarStatus?.latency_ms || 0} ms</span></p>
              <p>کد HTTP: <span className="text-white font-mono">{divarStatus?.status_code || '-'}</span></p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
