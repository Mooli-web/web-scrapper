import React, { useState, useEffect } from 'react';
import { Database, ShieldCheck, Trash2, HardDrive, RefreshCw, AlertTriangle } from 'lucide-react';
import { fetchDbSize, wipeDatabase } from '../api';
import DbTestModal from '../components/DbTestModal';

export default function DatabaseView() {
  const [dbData, setDbData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wiping, setWiping] = useState(false);
  const [isTestOpen, setIsTestOpen] = useState(false);

  const loadData = async () => {
    setLoading(true);
    const data = await fetchDbSize();
    setDbData(data);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleWipeDatabase = async () => {
    const confirmed = window.confirm(
      '⚠️ هشدار مهم:\nآیا مطمئن هستید که می‌خواهید تمام اطلاعات محصولات، قیمت‌ها و لاگ‌ها را پاک و دیتابیس را کاملاً صفر کنید؟'
    );
    if (!confirmed) return;

    setWiping(true);
    try {
      await wipeDatabase();
      alert('✅ تمام اطلاعات دیتابیس با موفقیت حذف و دیتابیس صفر شد.');
      window.location.reload();
    } catch (e) {
      alert('خطا در پاکسازی: ' + e);
    } finally {
      setWiping(false);
    }
  };

  const usagePercent = dbData?.usage_percent || 0.0;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-sky-950/60 via-slate-900/80 to-slate-900/90 border border-sky-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <HardDrive className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white">مدیریت پایگاه داده CockroachDB (Storage Management)</h2>
            <p className="text-xs text-slate-400">
              مدیریت حجم، سنجش پایداری در پلن رایگان ۵ گیگ و امکان صفر کردن کامل اطلاعات با ۱ کلیک
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsTestOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-400 border border-slate-700 text-xs font-bold transition cursor-pointer"
          >
            <Database className="w-4 h-4" />
            <span>تست زنده اتصال</span>
          </button>

          <button
            onClick={handleWipeDatabase}
            disabled={wiping}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-lg shadow-rose-600/30 cursor-pointer disabled:opacity-50"
          >
            <AlertTriangle className="w-4 h-4" />
            <span>{wiping ? 'در حال پاکسازی...' : 'حذف همه اطلاعات و صفر کردن دیتابیس'}</span>
          </button>
        </div>
      </div>

      {/* Quota Progress Card */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-white">مصرف واقعی فضای ذخیره‌سازی CockroachDB</span>
          <span className="text-slate-400 font-mono">
            {dbData?.estimated_storage_mb || 0} MB از {dbData?.quota_max_gb || 5} GB ({usagePercent}٪)
          </span>
        </div>

        <div className="w-full bg-slate-950 rounded-full h-3 relative overflow-hidden border border-slate-800 p-0.5">
          <div
            className="h-full rounded-full transition-all duration-500 bg-gradient-to-r from-sky-500 to-emerald-500"
            style={{ width: `${Math.min(100, Math.max(1, usagePercent))}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <span>۰ مگابایت (شروع)</span>
          <span className="text-emerald-400 font-semibold">سقف رایگان دائمی: ۵.۰ گیگابایت (CockroachDB Serverless)</span>
        </div>
      </div>

      {/* Table Breakdown Grid */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800">
        <h3 className="text-sm font-bold text-white mb-4">تفکیک رکوردهای پایگاه داده</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="pb-3 pr-2">نام جدول</th>
                <th className="pb-3">توضیحات جدول</th>
                <th className="pb-3">تعداد ردیف‌ها</th>
                <th className="pb-3">حجم تقریبی (MB)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {dbData?.tables && dbData.tables.map((t) => (
                <tr key={t.table_name} className="hover:bg-slate-900/60 transition font-mono text-[11px]">
                  <td className="py-3.5 pr-2 font-bold text-white">{t.table_name}</td>
                  <td className="py-3.5 font-vazir text-slate-400">
                    {t.table_name === 'master_products' ? 'کاتالوگ مرجع کالاها' :
                     t.table_name === 'store_listings' ? 'قیمت لحظه‌ای و وضعیت موجودی فروشگاه‌ها' :
                     t.table_name === 'price_observations' ? 'دفترکل انحصاری تغییرات قیمت (Delta Ledger)' :
                     t.table_name === 'price_events' ? 'رویدادهای افت قیمت و تخفیف‌ها' :
                     t.table_name === 'categories' ? 'درخت دسته‌بندی‌ها' : 'داده‌های ساختاری و لاگ‌ها'}
                  </td>
                  <td className="py-3.5 font-bold text-white">{t.row_count.toLocaleString('fa-IR')}</td>
                  <td className="py-3.5 text-sky-400 font-bold">{t.estimated_mb} MB</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <DbTestModal isOpen={isTestOpen} onClose={() => setIsTestOpen(false)} />
    </div>
  );
}
