import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Percent,
  Search,
  ExternalLink,
  AlertTriangle,
  Flame,
  Info,
  CheckCircle2,
  Clock,
  Sparkles
} from 'lucide-react';
import { fetchFakeDiscounts, formatToman, formatPercent } from '../api';

export default function FakeDiscounts() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, stats: {} });
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'fake', 'genuine', 'baseline'
  const [category, setCategory] = useState('all');
  const [minDiscount, setMinDiscount] = useState(5);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchFakeDiscounts({
      status: statusFilter,
      category: category !== 'all' ? category : undefined,
      min_claimed_discount: minDiscount,
      page,
      page_size: 20
    }).then((res) => {
      if (active) {
        setData(res);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [statusFilter, category, minDiscount, page]);

  const stats = data.stats || {};

  return (
    <div className="space-y-6">
      {/* Header & Concept */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shadow-lg shadow-amber-500/10">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white">آشکارساز تخفیف‌های ساختگی (Fake Discount Detector)</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                مقایسه درصد تخفیف ادعایی فروشگاه با میانگین وزنی ۳۰ روزه دفترکل برای افشای افزایش قیمت‌های ساختگی قبل از تخفیف
              </p>
            </div>
          </div>
          <span className="text-xs font-bold px-3 py-1.5 rounded-xl bg-slate-950 text-amber-400 border border-slate-800">
            موتور تحلیل اصالت قیمت فعال
          </span>
        </div>

        {/* Cold Start Informative Note */}
        <div className="p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800 flex items-start gap-2.5 text-xs text-slate-300">
          <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
          <p className="leading-relaxed text-[11px]">
            <strong>نحوه کارکرد الگوریتم:</strong> قیمت‌های اولیه هر کالا به عنوان <strong>«خط مبنا (Baseline)»</strong> ثبت می‌شوند. با گذشت زمان و پایش پیوسته ۲۴ ساعته، به محض اینکه فروشنده‌ای قیمت پایه را بالا ببرد و تخفیف صوری ثبت کند، سیستم با برچسب <strong>🔴 تخفیف فیک</strong> مبلغ دقیق حباب را افشا می‌کند.
          </p>
        </div>

        {/* Diagnostic KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
          <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 text-center space-y-1">
            <span className="text-[10px] text-slate-400 block font-medium">کالاهای بررسی‌شده با تخفیف</span>
            <strong className="text-lg font-black text-white font-mono">
              {Number(stats.total_analyzed || 0).toLocaleString('fa-IR')}
            </strong>
          </div>

          <div className="p-4 rounded-2xl bg-rose-950/20 border border-rose-500/30 text-center space-y-1">
            <div className="flex items-center justify-center gap-1 text-[10px] text-rose-400 font-bold">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>تخفیف‌های فیک (حباب‌دار)</span>
            </div>
            <strong className="text-lg font-black text-rose-400 font-mono">
              {Number(stats.fake_count || 0).toLocaleString('fa-IR')}
            </strong>
            <span className="text-[9px] text-rose-300/80 block font-mono">
              ({stats.fake_ratio_percent || 0}٪ کل تخفیف‌ها)
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 text-center space-y-1">
            <div className="flex items-center justify-center gap-1 text-[10px] text-emerald-400 font-bold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>تخفیف‌های طلایی و واقعی</span>
            </div>
            <strong className="text-lg font-black text-emerald-400 font-mono">
              {Number(stats.genuine_count || 0).toLocaleString('fa-IR')}
            </strong>
            <span className="text-[9px] text-emerald-300/80 block">ارزان‌تر از میانگین ۳۰ روزه</span>
          </div>

          <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 text-center space-y-1">
            <div className="flex items-center justify-center gap-1 text-[10px] text-sky-400 font-bold">
              <Clock className="w-3.5 h-3.5" />
              <span>ثبت قیمت مبنا (در حال ردیابی)</span>
            </div>
            <strong className="text-lg font-black text-sky-400 font-mono">
              {Number(stats.baseline_count || 0).toLocaleString('fa-IR')}
            </strong>
            <span className="text-[9px] text-slate-400 block">پایش اولیه نوسانات</span>
          </div>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="glass-card rounded-3xl p-5 border border-slate-800">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-slate-400 block mb-1 font-bold">نوع اصالت تخفیف:</label>
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 transition"
            >
              <option value="all">🔍 همه کالاهای تخفیف‌دار ({stats.total_analyzed || 0})</option>
              <option value="fake">🔴 فقط تخفیف‌های فیک و حباب‌دار ({stats.fake_count || 0})</option>
              <option value="genuine">🟢 فقط تخفیف‌های واقعی و طلایی ({stats.genuine_count || 0})</option>
              <option value="baseline">⚪ کالاهای در مرحله ثبت قیمت مبنا ({stats.baseline_count || 0})</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] text-slate-400 block mb-1 font-bold">دسته‌بندی بازار:</label>
            <select
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 transition"
            >
              <option value="all">همه دسته‌ها</option>
              <option value="mobile-apple">گوشی‌های اپل (iPhone)</option>
              <option value="mobile-samsung">گوشی‌های سامسونگ (Galaxy)</option>
              <option value="mobile-xiaomi">گوشی‌های شیائومی (Xiaomi)</option>
              <option value="laptop-asus">لپ‌تاپ‌های ایسوس (ASUS)</option>
              <option value="laptop-apple">مک‌بوک‌های اپل (MacBook)</option>
              <option value="laptop-lenovo">لپ‌تاپ‌های لنوو (Lenovo)</option>
              <option value="gaming-playstation">پلی‌استیشن ۵ (PS5)</option>
              <option value="graphic-cards">کارت گرافیک (GPU)</option>
              <option value="processors">پردازنده (CPU)</option>
              <option value="smart-watches">ساعت هوشمند</option>
              <option value="headphones">هدفون و هندزفری</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] text-slate-400 block mb-1 font-bold">حداقل درصد تخفیف ادعایی:</label>
            <select
              value={minDiscount}
              onChange={(e) => { setMinDiscount(Number(e.target.value)); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 transition"
            >
              <option value="5">حداقل ۵٪ تخفیف ادعایی</option>
              <option value="10">حداقل ۱۰٪ تخفیف ادعایی</option>
              <option value="20">حداقل ۲۰٪ تخفیف ادعایی</option>
              <option value="30">حداقل ۳۰٪ تخفیف ادعایی</option>
            </select>
          </div>
        </div>
      </div>

      {/* Items Table */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800">
        {loading ? (
          <div className="py-20 text-center space-y-2">
            <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400">در حال تحلیل اصالت تخفیف‌ها با داده‌های دفترکل...</p>
          </div>
        ) : data.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-bold">
                  <th className="pb-3 text-right">کالا و مشخصات</th>
                  <th className="pb-3 text-center">فروشنده</th>
                  <th className="pb-3 text-right">قیمت فعلی فروش</th>
                  <th className="pb-3 text-center">تخفیف ادعایی</th>
                  <th className="pb-3 text-right">میانگین واقعی ۳۰ روزه</th>
                  <th className="pb-3 text-center">وضعیت اصالت تخفیف</th>
                  <th className="pb-3 text-center">لینک مستقیم</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.items.map((prod) => {
                  const isFake = prod.authenticity_status === 'FAKE';
                  const isGolden = prod.authenticity_status === 'GENUINE_GOLDEN';
                  const isReal = prod.authenticity_status === 'REAL_DEAL';

                  return (
                    <tr key={prod.product_id} className={`hover:bg-slate-800/30 transition ${isFake ? 'bg-rose-950/10' : ''}`}>
                      <td className="py-3.5 pr-1">
                        <div className="flex items-center gap-3">
                          {prod.image_url ? (
                            <img
                              src={prod.image_url}
                              alt={prod.title_fa}
                              className="w-11 h-11 rounded-xl object-contain bg-white/5 p-1 border border-slate-800 shrink-0"
                              onError={(e) => { e.target.style.display = 'none'; }}
                            />
                          ) : (
                            <div className="w-11 h-11 rounded-xl bg-slate-800 border border-slate-700 shrink-0" />
                          )}
                          <div className="space-y-0.5 max-w-sm">
                            <a href={prod.product_url} target="_blank" rel="noopener noreferrer" className="font-bold text-white hover:text-rose-400 transition line-clamp-1 block" title={prod.title_fa}>
                              {prod.title_fa}
                            </a>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400">
                              <span className="font-semibold text-slate-300">{prod.brand || 'متفرقه'}</span>
                              <span>•</span>
                              <span>{prod.category_name || 'کالای دیجیتال'}</span>
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 text-center">
                        <span className="text-slate-300 text-[11px] font-semibold">{prod.seller_name || 'دیجی‌کالا'}</span>
                      </td>
                      <td className="py-3.5">
                        <div className="space-y-0.5">
                          <span className="font-mono font-bold text-white text-sm block">
                            {formatToman(prod.selling_price_toman)}
                          </span>
                          {prod.rrp_price_toman > prod.selling_price_toman && (
                            <span className="font-mono text-[10px] text-slate-500 line-through block">
                              ادعای اولیه: {formatToman(prod.rrp_price_toman)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 text-center">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 font-mono font-bold text-xs border border-rose-500/30">
                          {formatPercent(prod.claimed_discount)}
                        </span>
                      </td>
                      <td className="py-3.5">
                        <span className="font-mono font-semibold text-sky-400 text-xs">
                          {formatToman(prod.avg_price_30d)}
                        </span>
                      </td>
                      <td className="py-3.5 text-center">
                        {isFake ? (
                          <div className="inline-flex flex-col items-center p-1.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 space-y-0.5">
                            <div className="flex items-center gap-1 font-bold text-[10px]">
                              <AlertTriangle className="w-3 h-3" />
                              <span>تخفیف فیک (حباب‌دار)</span>
                            </div>
                            <span className="text-[9px] text-rose-300 font-mono">
                              +{formatToman(prod.inflation_margin_toman)} گران‌تر از میانگین!
                            </span>
                          </div>
                        ) : isGolden ? (
                          <div className="inline-flex flex-col items-center p-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 space-y-0.5">
                            <div className="flex items-center gap-1 font-bold text-[10px]">
                              <Flame className="w-3 h-3 fill-emerald-400" />
                              <span>تخفیف طلایی</span>
                            </div>
                            <span className="text-[9px] text-emerald-300 font-mono">
                              کمترین قیمت ۳۰ روزه
                            </span>
                          </div>
                        ) : isReal ? (
                          <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-400 font-bold text-[10px]">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>تخفیف معتبر ({prod.real_discount_vs_avg}٪ واقعی)</span>
                          </div>
                        ) : (
                          <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-slate-800 text-slate-400 border border-slate-700 text-[10px]">
                            <Clock className="w-3 h-3 text-slate-500" />
                            <span>ثبت قیمت مبنا</span>
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 text-center">
                        <a
                          href={prod.product_url || `https://www.digikala.com/product/dkp-${prod.product_id}/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-bold transition"
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
            <ShieldCheck className="w-12 h-12 text-emerald-500/40 mx-auto" />
            <h4 className="text-sm font-bold text-white">هیچ تخفیف ساختگی در این فیلتر ثبت نشده است</h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
              تمامی کالاهای دارای تخفیف در حال حاضر بر اساس قیمت مبنا معتبر هستند. با پایش مداوم بازار، به محض شناسایی افزایش قیمت صوری، در این جدول گزارش خواهد شد.
            </p>
          </div>
        )}

        {/* Pagination */}
        {data.total > 20 && (
          <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-800 text-xs text-slate-400">
            <span>صفحه {page} (مجموع {data.total} کالا)</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition cursor-pointer"
              >
                صفحه قبلی
              </button>
              <button
                disabled={page * 20 >= data.total}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition cursor-pointer"
              >
                صفحه بعدی
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
