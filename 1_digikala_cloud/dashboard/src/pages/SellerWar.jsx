import React, { useState, useEffect } from 'react';
import {
  Swords,
  Trophy,
  Users,
  TrendingDown,
  ExternalLink,
  Flame,
  Zap,
  Award,
  Sparkles,
  Info,
  CheckCircle2
} from 'lucide-react';
import { fetchSellerWars, formatToman, formatPercent } from '../api';

export default function SellerWar() {
  const [data, setData] = useState({ battles: [], top_sellers: [], total_battles: 0 });
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('all');

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchSellerWars({
      category: category !== 'all' ? category : undefined
    }).then((res) => {
      if (active) {
        setData(res);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [category]);

  const battles = data.battles || [];
  const topSellers = data.top_sellers || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 shadow-lg shadow-rose-500/10">
              <Swords className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white">رصد جنگ قیمت فروشندگان و بای‌باکس (Seller War & Buy Box)</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                شناسایی رقابت‌های لحظه‌ای و شکستن قیمت بین فروشندگان دیجی‌کالا برای تصاحب سبد خرید اصلی
              </p>
            </div>
          </div>
          <span className="text-xs font-bold px-3 py-1.5 rounded-xl bg-slate-950 text-rose-400 border border-slate-800">
            {battles.length} کالای رقابتی پایش‌شده
          </span>
        </div>

        {/* Informative Note */}
        <div className="p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800 flex items-start gap-2.5 text-xs text-slate-300">
          <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
          <p className="leading-relaxed text-[11px]">
            <strong>بای‌باکس (Buy Box چیست؟):</strong> در مارکت‌پلیس دیجی‌کالا، فروشنده‌ای که بهترین قیمت و امتیاز را داشته باشد برنده دکمه «افزودن به سبد خرید» می‌شود. این ابزار تغییرات برندگان بای‌باکس و کاهش‌های رقابتی قیمت را لحظه‌به‌لحظه ثبت می‌کند.
          </p>
        </div>

        {/* Category Selector */}
        <div className="pt-1">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full sm:w-72 bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500 transition font-medium"
          >
            <option value="all">همه دسته‌بندی‌ها</option>
            <option value="mobile-apple">گوشی‌های اپل (iPhone)</option>
            <option value="mobile-samsung">گوشی‌های سامسونگ (Galaxy)</option>
            <option value="mobile-xiaomi">گوشی‌های شیائومی (Xiaomi)</option>
            <option value="laptop-asus">لپ‌تاپ‌های ایسوس (ASUS)</option>
            <option value="laptop-apple">مک‌بوک‌های اپل (MacBook)</option>
            <option value="gaming-playstation">پلی‌استیشن ۵ (PS5)</option>
            <option value="graphic-cards">کارت گرافیک (GPU)</option>
            <option value="processors">پردازنده (CPU)</option>
          </select>
        </div>
      </div>

      {/* Top Aggressive Sellers Leaderboard */}
      {topSellers.length > 0 && (
        <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-black text-white">برترین فروشندگان در تصاحب باکس خرید (Top Buy Box Winners)</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {topSellers.slice(0, 4).map((seller, idx) => (
              <div key={seller.seller_name} className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-black ${
                      idx === 0 ? 'bg-amber-500 text-slate-950 font-bold' : 'bg-slate-800 text-slate-300'
                    }`}>
                      #{idx + 1}
                    </span>
                    <span className="font-bold text-white text-xs truncate max-w-[130px]">{seller.seller_name}</span>
                  </div>
                  <Award className={`w-4 h-4 ${idx === 0 ? 'text-amber-400' : 'text-slate-600'}`} />
                </div>

                <div className="grid grid-cols-2 gap-2 text-center text-xs pt-1">
                  <div className="p-2 rounded-xl bg-slate-900 border border-slate-800/80">
                    <span className="text-[9px] text-slate-400 block">برنده سبد خرید</span>
                    <span className="font-mono font-bold text-emerald-400 text-xs">{seller.buybox_won_count} کالا</span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-900 border border-slate-800/80">
                    <span className="text-[9px] text-slate-400 block">میانگین تخفیف</span>
                    <span className="font-mono font-bold text-rose-400 text-xs">{formatPercent(seller.avg_discount_offered)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Battles Table */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-rose-400" />
            <h3 className="text-sm font-black text-white">لیست کالاهای درگیر جنگ قیمتی و برندگان سبد خرید</h3>
          </div>
        </div>

        {loading ? (
          <div className="py-20 text-center space-y-2">
            <div className="w-8 h-8 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400">در حال ردیابی نبردهای قیمتی فروشندگان...</p>
          </div>
        ) : battles.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-bold">
                  <th className="pb-3 text-right">کالای رقابتی</th>
                  <th className="pb-3 text-center">برنده فعلی Buy Box</th>
                  <th className="pb-3 text-right">قیمت برنده سبد خرید</th>
                  <th className="pb-3 text-center">فروشندگان درگیر</th>
                  <th className="pb-3 text-center">دفعات تغییر قیمت</th>
                  <th className="pb-3 text-right">کمترین قیمت ۳۰ روزه</th>
                  <th className="pb-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {battles.map((b) => {
                  const isMulti = Number(b.competing_sellers_count || 1) > 1;
                  return (
                    <tr key={b.product_id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 pr-1">
                        <div className="flex items-center gap-3">
                          {b.image_url ? (
                            <img
                              src={b.image_url}
                              alt={b.title_fa}
                              className="w-11 h-11 rounded-xl object-contain bg-white/5 p-1 border border-slate-800 shrink-0"
                              onError={(e) => { e.target.style.display = 'none'; }}
                            />
                          ) : (
                            <div className="w-11 h-11 rounded-xl bg-slate-800 border border-slate-700 shrink-0" />
                          )}
                          <div className="space-y-0.5 max-w-sm">
                            <a href={b.product_url} target="_blank" rel="noopener noreferrer" className="font-bold text-white hover:text-rose-400 transition line-clamp-1 block" title={b.title_fa}>
                              {b.title_fa}
                            </a>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400">
                              <span className="font-semibold text-slate-300">{b.brand || 'متفرقه'}</span>
                              <span>•</span>
                              <span>{b.category_name || 'کالای دیجیتال'}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 text-center">
                        <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold text-xs">
                          <Trophy className="w-3 h-3 text-emerald-400" />
                          <span>{b.buybox_winner || 'دیجی‌کالا'}</span>
                        </div>
                      </td>

                      <td className="py-3.5">
                        <div className="space-y-0.5">
                          <span className="font-mono font-bold text-white text-sm block">
                            {formatToman(b.buybox_price)}
                          </span>
                          {b.discount_percent > 0 && (
                            <span className="inline-block text-[10px] text-rose-400 font-mono font-semibold">
                              {formatPercent(b.discount_percent)} تخفیف رقابتی
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5 text-center">
                        {isMulti ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 font-mono font-bold text-xs">
                            <Users className="w-3 h-3 text-rose-400" />
                            <span>{b.competing_sellers_count} فروشنده در رقابت</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 text-[10px]">
                            تک‌فروشنده فعال
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 text-center">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-900 text-slate-300 border border-slate-800 text-[10px] font-bold">
                          <TrendingDown className="w-3 h-3 text-amber-400" />
                          <span>{b.total_price_drops || 0} افت قیمت</span>
                        </span>
                      </td>

                      <td className="py-3.5">
                        <span className="font-mono font-semibold text-emerald-400 text-xs">
                          {formatToman(b.min_price_30d)}
                        </span>
                      </td>

                      <td className="py-3.5 text-center">
                        <a
                          href={b.product_url || `https://www.digikala.com/product/dkp-${b.product_id}/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-slate-800 hover:bg-rose-600 hover:text-white text-slate-300 text-[11px] font-bold transition border border-slate-700"
                        >
                          <span>مشاهده</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-16 space-y-3">
            <Swords className="w-12 h-12 text-slate-600 mx-auto" />
            <h4 className="text-sm font-bold text-white">در حال حاضر نبرد قیمتی شدیدی ثبت نشده است</h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              با تداوم خزش پیوسته، به محض اینکه فروشنده‌ای برای تصاحب بای‌باکس قیمت را بشکند، در این جدول ثبت خواهد شد.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
