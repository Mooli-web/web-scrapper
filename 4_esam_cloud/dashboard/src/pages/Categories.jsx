import React, { useState, useEffect } from 'react';
import { Layers, RefreshCw, Play, CheckCircle2, Gavel, Cpu, HardDrive, Smartphone, Gamepad } from 'lucide-react';
import { fetchEsamCategories, triggerCrawlerBatch } from '../api';

export default function Categories() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [triggeringKey, setTriggeringKey] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchEsamCategories();
      setCategories(res.categories || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleScrapeNow = async (catKey) => {
    setTriggeringKey(catKey);
    try {
      await triggerCrawlerBatch(catKey, 1);
      await loadData();
    } catch (e) {
      alert('خطا در اجرای اسکرپ دسته: ' + e.message);
    } finally {
      setTriggeringKey(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-white">دسته‌بندی‌های هدف خزش ایسام (Esam Categories)</h1>
          <p className="text-xs text-slate-400 mt-1">
            مدیریت فیدهای مزایدات و شاخه‌های هدف استوک و سخت‌افزار با قابلیت تریگر دستی خزش
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>بروزرسانی دسته‌ها</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.map((cat) => (
          <div
            key={cat.id || cat.category_key}
            className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm shadow-md flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-bold text-white line-clamp-1">{cat.title_fa}</span>
                {cat.is_auction_feed ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    فید مزایده
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-400">
                    cc={cat.category_code}
                  </span>
                )}
              </div>

              <p className="text-[11px] font-mono text-slate-400 truncate mb-3" dir="ltr">
                /{cat.query_slug}
              </p>

              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-400">کالاهای ثبت‌شده:</span>
                <span className="font-extrabold text-orange-400 font-mono">
                  {Number(cat.real_items_count || 0).toLocaleString('fa-IR')} کالا
                </span>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <span className="flex items-center gap-1 text-[11px] text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                پایش فعال
              </span>

              <button
                onClick={() => handleScrapeNow(cat.category_key)}
                disabled={triggeringKey === cat.category_key}
                className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-orange-600/20 hover:bg-orange-600/30 text-orange-400 border border-orange-500/30 text-xs font-bold transition disabled:opacity-50"
              >
                {triggeringKey === cat.category_key ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 fill-current" />
                )}
                <span>خزش فوری (صفحه ۱)</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
