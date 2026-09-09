import React, { useState, useEffect } from 'react';
import { Package, Flame, Percent, Activity, Sparkles, ExternalLink, Layers, CheckCircle2, Clock, ShieldAlert, Swords, ArrowLeft } from 'lucide-react';
import StatCard from '../components/StatCard';
import SeverityBadge from '../components/SeverityBadge';
import LiveMissionControl from '../components/LiveMissionControl';
import { fetchOverview, formatToman, formatPercent, formatPersianDate } from '../api';

export default function Overview({ onNavigateToProducts, onNavigateToFakeDiscounts, onNavigateToSellerWar }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    let active = true;
    fetchOverview().then((res) => {
      if (active) {
        setData(res);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [refreshTrigger]);

  const handleRefresh = () => {
    setRefreshTrigger((c) => c + 1);
  };

  return (
    <div className="space-y-6">
      {/* Live Mission Control Bar */}
      <LiveMissionControl onStatusChange={handleRefresh} />

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کالاهای دیجیتال در کاتالوگ"
          value={data ? Number(data.total_products).toLocaleString('fa-IR') : '۰'}
          subtitle={`موجودی در انبار: ${data ? Number(data.in_stock_count).toLocaleString('fa-IR') : '۰'}`}
          icon={Package}
          color="rose"
          trend={{ positive: true, text: 'استخراج زنده و پیوسته', label: 'دیجی‌کالا' }}
        />
        <StatCard
          title="افت قیمت ۲۴ ساعت اخیر"
          value={data ? Number(data.events_24h).toLocaleString('fa-IR') : '۰'}
          subtitle={`افت شدید: ${data ? Number(data.high_severity_24h).toLocaleString('fa-IR') : '۰'} کالا`}
          icon={Flame}
          color="amber"
          trend={{ positive: true, text: 'سیگنال واقعی', label: 'دفترکل قیمت' }}
        />
        <StatCard
          title="تخفیف‌های فعال بازار"
          value={data ? Number(data.active_discounts).toLocaleString('fa-IR') : '۰'}
          subtitle={`میانگین تخفیف: ${data ? formatPercent(data.avg_discount_percent) : '۰٪'}`}
          icon={Percent}
          color="emerald"
          trend={{ positive: true, text: 'سود خرید', label: 'نسبت به قیمت فروشنده' }}
        />
        <StatCard
          title="فضای مصرفی دیتابیس"
          value={data ? `${data.db_size_mb} MB` : '۰ MB'}
          subtitle={`پلن ۵ گیگ CockroachDB`}
          icon={Activity}
          color="sky"
          trend={{ positive: true, text: 'ذخیره دلتا', label: 'حجم پایدار' }}
        />
      </div>

      {/* Quick Access Intelligence Banners */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Fake Discount Banner */}
        <div className="glass-card rounded-3xl p-5 border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-amber-950/20 hover:border-amber-500/40 transition flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-black text-white">آشکارساز تخفیف فیک (Fake Discount Detector)</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                تخفیف‌های فیک شناسایی‌شده: <strong className="text-amber-400 font-mono">{Number(data?.fake_discounts_count || 0).toLocaleString('fa-IR')}</strong> کالا
              </p>
            </div>
          </div>
          <button
            onClick={onNavigateToFakeDiscounts}
            className="flex items-center gap-1 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-amber-600 text-slate-200 hover:text-white text-xs font-bold transition shrink-0 cursor-pointer"
          >
            <span>بررسی</span>
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Seller War Banner */}
        <div className="glass-card rounded-3xl p-5 border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-rose-950/20 hover:border-rose-500/40 transition flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 shrink-0">
              <Swords className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-black text-white">جنگ قیمت فروشندگان (Seller Price War & Buy Box)</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                رصد برندگان سبد خرید اصلی و شکستن قیمت بین فروشندگان
              </p>
            </div>
          </div>
          <button
            onClick={onNavigateToSellerWar}
            className="flex items-center gap-1 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-rose-600 text-slate-200 hover:text-white text-xs font-bold transition shrink-0 cursor-pointer"
          >
            <span>مشاهده نبردها</span>
            <ArrowLeft className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Recent Deep Price Drops Feed */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-bold text-white">آخرین افت قیمت‌های شناسایی‌شده در بازار</h3>
          </div>
          <span className="text-xs text-slate-400">لینک مستقیم به صفحه خرید در دیجی‌کالا</span>
        </div>

        {data?.recent_deals && data.recent_deals.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.recent_deals.map((deal) => (
              <div
                key={deal.id || deal.product_id}
                className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-rose-500/40 transition flex flex-col justify-between gap-3 group"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[10px] font-black">
                      {formatPercent(deal.drop_percent)} افت قیمت
                    </span>
                    <span className="text-[10px] text-slate-400">{deal.brand}</span>
                  </div>
                  <a
                    href={deal.product_url || `https://www.digikala.com/product/dkp-${deal.product_id}/`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-bold text-white group-hover:text-rose-400 transition line-clamp-2 block"
                  >
                    {deal.title_fa}
                  </a>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-emerald-400 block">{formatToman(deal.new_price_toman)}</span>
                    <span className="text-[10px] text-slate-500 line-through">{formatToman(deal.old_price_toman)}</span>
                  </div>

                  <a
                    href={deal.product_url || `https://www.digikala.com/product/dkp-${deal.product_id}/`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-bold flex items-center gap-1 transition"
                  >
                    <span>دیجی‌کالا</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 space-y-2">
            <p className="text-xs text-slate-400">هنوز افت قیمتی در دیتابیس ثبت نشده است.</p>
            <p className="text-[11px] text-slate-500">برای استخراج زندهٔ کالاهای الکترونیک، دکمهٔ «شروع پایش پیوسته بازار» را کلیک کنید.</p>
          </div>
        )}
      </div>
    </div>
  );
}
