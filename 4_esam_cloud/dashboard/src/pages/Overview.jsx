import React, { useState, useEffect } from 'react';
import { ShoppingBag, Gavel, TrendingDown, Layers, ShieldCheck, Activity, Cpu, Sparkles, RefreshCw } from 'lucide-react';
import StatCard from '../components/StatCard';
import { fetchOverviewStats } from '../api';

export default function Overview({ onNavigate }) {
  const [stats, setStats] = useState({
    total_items: 0,
    total_auctions: 0,
    total_events: 0,
    price_drops_24h: 0,
    avg_price_toman: 0,
    categories_breakdown: [],
    conditions_breakdown: []
  });
  const [loading, setLoading] = useState(true);

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await fetchOverviewStats();
      setStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-white">داشبورد هوش و مانیتورینگ ایسام (Esam Intelligence)</h1>
          <p className="text-xs text-slate-400 mt-1">
            پایش هوشمند بازار مزایدات آنلاین، کالاهای استوک، قطعات سخت‌افزار و قیمت کف بازار
          </p>
        </div>
        <button
          onClick={loadStats}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>بروزرسانی داده‌ها</span>
        </button>
      </div>

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل کالاهای پایش‌شده ایسام"
          value={stats.total_items}
          unit="کالا"
          icon={ShoppingBag}
          color="orange"
          subtext="کالاهای نو، در حد نو، استوک و دست‌دوم"
        />
        <StatCard
          title="مزایدات فعال و لحظه‌ای"
          value={stats.total_auctions}
          unit="مزایده"
          icon={Gavel}
          color="amber"
          subtext="دارای مهلت زمانی و سیستم ثبت پیشنهاد"
        />
        <StatCard
          title="افت قیمت‌های ۲۴ ساعت گذشته"
          value={stats.price_drops_24h}
          unit="مورد"
          icon={TrendingDown}
          color="emerald"
          subtext="فرصت‌های خرید با قیمت کاهش‌یافته"
        />
        <StatCard
          title="میانگین قیمت کالاهای دیجیتال"
          value={stats.avg_price_toman}
          unit="تومان"
          icon={Cpu}
          color="sky"
          subtext="میانگین کل قیمت اقلام فعال در ایسام"
        />
      </div>

      {/* Breakdowns Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Categories Breakdown */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-orange-400" />
              <h3 className="text-sm font-bold text-white">توزیع کالاها در دسته‌بندی‌های هدف</h3>
            </div>
            <button
              onClick={() => onNavigate && onNavigate('categories')}
              className="text-xs text-orange-400 hover:underline font-semibold"
            >
              مشاهده همه
            </button>
          </div>

          {stats.categories_breakdown && stats.categories_breakdown.length > 0 ? (
            <div className="space-y-3">
              {stats.categories_breakdown.map((cat, idx) => (
                <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
                  <span className="font-semibold text-slate-200">{cat.name || 'دسته‌بندی'}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-slate-400 font-mono">{Number(cat.count || 0).toLocaleString('fa-IR')} کالا</span>
                    {cat.avg_price > 0 && (
                      <span className="font-bold text-orange-400">
                        {Number(Math.round(cat.avg_price)).toLocaleString('fa-IR')} ت
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-500 rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
              داده‌ای برای نمایش وجود ندارد. با زدن دکمه «شروع خزش پیوسته ایسام»، ورکر شروع به جمع‌آوری کالاها می‌کند.
            </div>
          )}
        </div>

        {/* Condition Distribution Breakdown */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">تفکیک وضعیت سلامت فنی اقلام ایسام</h3>
            </div>
          </div>

          {stats.conditions_breakdown && stats.conditions_breakdown.length > 0 ? (
            <div className="space-y-3">
              {stats.conditions_breakdown.map((cond, idx) => (
                <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs">
                  <span className="font-semibold text-slate-200">{cond.name || 'نامشخص'}</span>
                  <span className="font-bold text-emerald-400 font-mono">
                    {Number(cond.count || 0).toLocaleString('fa-IR')} کالا
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-500 rounded-xl bg-slate-950/40 border border-dashed border-slate-800">
              در انتظار خزش و تفکیک وضعیت‌های سلامت اقلام...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
