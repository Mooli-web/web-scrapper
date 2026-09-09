import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  ExternalLink,
  X,
  PackageCheck,
  PackageX,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Globe,
  Store,
  Users
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

import PriceBadge from '../components/PriceBadge';
import { fetchProducts, fetchProductDetail, formatToman, formatPercent, formatPersianDate } from '../api';

export default function Products({ initialCategory = 'all' }) {
  const [productsData, setProductsData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [loading, setLoading] = useState(true);

  // Filters & Sorting State
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState(initialCategory || 'all');
  const [minDiscount, setMinDiscount] = useState(0);
  const [inStockOnly, setInStockOnly] = useState(false);
  const [sortBy, setSortBy] = useState('discount_desc');
  const [page, setPage] = useState(1);

  // Detail Modal
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productDetail, setProductDetail] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);

  useEffect(() => {
    if (initialCategory && initialCategory !== 'all') {
      setCategory(initialCategory);
    }
  }, [initialCategory]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchProducts({
      search: search.trim() || undefined,
      category: category !== 'all' ? category : undefined,
      min_discount: minDiscount > 0 ? minDiscount : undefined,
      in_stock_only: inStockOnly,
      sort_by: sortBy,
      page,
      page_size: 20
    }).then((res) => {
      if (active) {
        setProductsData(res);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [search, category, minDiscount, inStockOnly, sortBy, page]);

  const openProductDetail = async (prod) => {
    setSelectedProduct(prod);
    setModalLoading(true);
    const detail = await fetchProductDetail(prod.product_id);
    setProductDetail(detail);
    setModalLoading(false);
  };

  const toggleSort = (field) => {
    if (field === 'price') {
      setSortBy((prev) => prev === 'price_asc' ? 'price_desc' : 'price_asc');
    } else if (field === 'discount') {
      setSortBy((prev) => prev === 'discount_desc' ? 'newest' : 'discount_desc');
    } else if (field === 'title') {
      setSortBy((prev) => prev === 'title_asc' ? 'newest' : 'title_asc');
    }
    setPage(1);
  };

  const chartHistory = useMemo(() => {
    if (!productDetail?.history || productDetail.history.length === 0) {
      if (selectedProduct) {
        return [{ date: 'فعلی', price: selectedProduct.selling_price_toman }];
      }
      return [];
    }
    return productDetail.history.map((h) => ({
      date: formatPersianDate(h.observed_at),
      price: h.selling_price_toman,
      rrp: h.rrp_price_toman
    }));
  }, [productDetail, selectedProduct]);

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-black text-white">دفترکل و کاتالوگ جامع محصولات (Products Ledger)</h2>
            <p className="text-xs text-slate-400">
              پایش زنده قیمت، فروشنده فعال و هدایت مستقیم به صفحه رسمی خرید کالا در دیجی‌کالا
            </p>
          </div>
          <span className="text-xs font-bold px-3 py-1 rounded-xl bg-slate-800 text-rose-400 border border-slate-700">
            مجموع: {productsData.total.toLocaleString('fa-IR')} محصول
          </span>
        </div>

        {/* Filter Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 pt-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-4 h-4 absolute right-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="جستجو در عنوان، برند یا فروشنده..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl pr-9 pl-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 transition"
            />
          </div>

          {/* Category Filter */}
          <div>
            <select
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500 transition font-medium"
            >
              <option value="all">همه دسته‌ها</option>
              <option value="mobile-apple">گوشی‌های اپل (iPhone)</option>
              <option value="mobile-samsung">گوشی‌های سامسونگ (Galaxy)</option>
              <option value="mobile-xiaomi">گوشی‌های شیائومی (Xiaomi)</option>
              <option value="laptop-asus">لپ‌تاپ‌های ایسوس (ASUS)</option>
              <option value="laptop-apple">مک‌بوک‌های اپل (MacBook)</option>
              <option value="laptop-lenovo">لپ‌تاپ‌های لنوو (Lenovo)</option>
              <option value="gaming-playstation">پلی‌استیشن ۵ (PS5)</option>
              <option value="gaming-xbox">ایکس‌باکس (Xbox)</option>
              <option value="graphic-cards">کارت گرافیک (GPU)</option>
              <option value="processors">پردازنده (CPU)</option>
              <option value="smart-watches">ساعت هوشمند</option>
              <option value="headphones">هدفون و هندزفری</option>
              <option value="storage-devices">حافظه SSD و هارد</option>
            </select>
          </div>

          {/* Sort By Filter */}
          <div>
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500 transition font-medium"
            >
              <option value="discount_desc">🔥 بیشترین تخفیف</option>
              <option value="price_asc">💰 ارزان‌ترین قیمت</option>
              <option value="price_desc">💎 گران‌ترین قیمت</option>
              <option value="newest">🕒 جدیدترین‌های کشف‌شده</option>
              <option value="title_asc">🔤 عنوان (الفبا)</option>
            </select>
          </div>

          {/* Min Discount */}
          <div>
            <select
              value={minDiscount}
              onChange={(e) => { setMinDiscount(Number(e.target.value)); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500 transition"
            >
              <option value="0">حداقل تخفیف: همه</option>
              <option value="5">حداقل ۵٪ تخفیف</option>
              <option value="10">حداقل ۱۰٪ تخفیف</option>
              <option value="20">حداقل ۲۰٪ تخفیف</option>
            </select>
          </div>

          {/* In Stock Toggle */}
          <label className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-950/80 border border-slate-700/80 text-xs text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(e) => { setInStockOnly(e.target.checked); setPage(1); }}
              className="w-4 h-4 rounded text-rose-600 focus:ring-rose-500 bg-slate-800 border-slate-700"
            />
            <span>فقط کالاهای موجود</span>
          </label>
        </div>
      </div>

      {/* Products Table */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800">
        {loading ? (
          <div className="py-20 text-center space-y-2">
            <div className="w-8 h-8 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400">در حال بارگذاری دفترکل کاتالوگ...</p>
          </div>
        ) : productsData.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-bold">
                  <th className="pb-3 text-right">محصول و برند</th>
                  <th className="pb-3 text-center">فروشنده فعال (Buy Box)</th>
                  <th className="pb-3 text-right cursor-pointer select-none hover:text-white" onClick={() => toggleSort('price')}>
                    <div className="flex items-center gap-1">
                      <span>قیمت فروش (تومان)</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-500" />
                    </div>
                  </th>
                  <th className="pb-3 text-right cursor-pointer select-none hover:text-white" onClick={() => toggleSort('discount')}>
                    <div className="flex items-center gap-1">
                      <span>تخفیف</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-500" />
                    </div>
                  </th>
                  <th className="pb-3 text-right">کمترین ۳۰ روزه</th>
                  <th className="pb-3 text-center">لینک مستقیم</th>
                  <th className="pb-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {productsData.items.map((prod) => {
                  const targetUrl = prod.product_url || `https://www.digikala.com/product/dkp-${prod.product_id}/`;

                  return (
                    <tr key={prod.product_id} className="hover:bg-slate-800/30 transition">
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
                            <a
                              href={targetUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-bold text-white hover:text-rose-400 transition line-clamp-1 block"
                              title={prod.title_fa}
                            >
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
                        <div className="space-y-1">
                          <span className="text-slate-200 font-bold text-[11px] block">{prod.seller_name || 'دیجی‌کالا'}</span>
                          {prod.available ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <PackageCheck className="w-2.5 h-2.5" />
                              <span>موجود</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                              <PackageX className="w-2.5 h-2.5" />
                              <span>ناموجود</span>
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5">
                        <div className="space-y-0.5">
                          <span className="font-mono font-bold text-white text-sm block">
                            {formatToman(prod.selling_price_toman)}
                          </span>
                          {prod.rrp_price_toman > prod.selling_price_toman && (
                            <span className="font-mono text-[10px] text-slate-500 line-through block">
                              {formatToman(prod.rrp_price_toman)}
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5">
                        <PriceBadge discount={prod.discount_percent} />
                      </td>

                      <td className="py-3.5">
                        <span className="font-semibold text-emerald-400 font-mono text-xs">{formatToman(prod.min_price_30d)}</span>
                      </td>

                      <td className="py-3.5 text-center">
                        <a
                          href={targetUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-rose-600/20 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/30 text-[11px] font-bold transition"
                        >
                          <span>دیجی‌کالا</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </td>

                      <td className="py-3.5 text-center">
                        <button
                          onClick={() => openProductDetail(prod)}
                          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-semibold transition cursor-pointer"
                        >
                          نمودار قیمت
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-16 space-y-3">
            <PackageX className="w-12 h-12 text-slate-600 mx-auto" />
            <h4 className="text-sm font-bold text-white">هنوز کالایی در دیتابیس ثبت نشده است</h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              برای شروع اسکن و استخراج واقعی کالاها از دیجی‌کالا، در صفحه اصلی دکمهٔ «شروع پایش پیوسته بازار» را بزنید.
            </p>
          </div>
        )}

        {/* Pagination Bar */}
        {productsData.total_pages > 1 && (
          <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-800 text-xs text-slate-400">
            <span>صفحه {page} از {productsData.total_pages}</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition cursor-pointer"
              >
                صفحه قبلی
              </button>
              <button
                disabled={page >= productsData.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition cursor-pointer"
              >
                صفحه بعدی
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Historical Price Chart Modal with Competing Sellers */}
      {selectedProduct && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card bg-slate-900 border border-slate-700 rounded-3xl p-6 max-w-2xl w-full space-y-4 relative">
            <button
              onClick={() => { setSelectedProduct(null); setProductDetail(null); }}
              className="absolute left-4 top-4 text-slate-400 hover:text-white p-1 rounded-lg bg-slate-800 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-400">
                تاریخچه، نوسان و رقابت فروشندگان
              </span>
              <h3 className="text-sm font-bold text-white mt-1 pr-6">{selectedProduct.title_fa}</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                برند: {selectedProduct.brand} | فروشنده فعلی: {selectedProduct.seller_name || 'دیجی‌کالا'}
              </p>
            </div>

            {/* Current Price vs Lowest */}
            <div className="grid grid-cols-3 gap-3 p-3 rounded-2xl bg-slate-950/80 border border-slate-800 text-center">
              <div>
                <span className="text-[10px] text-slate-400 block">قیمت فعلی</span>
                <span className="text-xs font-bold text-white">{formatToman(selectedProduct.selling_price_toman)}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">کمترین ۳۰ روزه</span>
                <span className="text-xs font-bold text-emerald-400">{formatToman(selectedProduct.min_price_30d)}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">میانگین ۳۰ روزه</span>
                <span className="text-xs font-bold text-sky-400">{formatToman(selectedProduct.avg_price_30d)}</span>
              </div>
            </div>

            {/* Competing Sellers List */}
            {productDetail?.competing_sellers && productDetail.competing_sellers.length > 0 && (
              <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="text-[10px] font-bold text-slate-400 block">فروشندگان ثبت‌شده در دفترکل برای این کالا:</span>
                <div className="flex flex-wrap gap-1.5">
                  {productDetail.competing_sellers.map((s) => (
                    <span key={s.seller_name} className="px-2.5 py-1 rounded-lg bg-slate-800 text-[10px] text-slate-300 border border-slate-700">
                      {s.seller_name}: <strong className="text-emerald-400">{formatToman(s.lowest_offered_price)}</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Price Line Chart */}
            <div className="h-56 w-full" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} />
                  <YAxis stroke="#94a3b8" fontSize={10} tickFormatter={(val) => `${(val / 1000000).toFixed(1)}M`} />
                  <Tooltip
                    formatter={(value) => [formatToman(value), 'قیمت']}
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }}
                  />
                  <Line type="monotone" dataKey="price" stroke="#ef394e" strokeWidth={3} dot={{ r: 4, fill: '#ef394e' }} name="قیمت فروش" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800">
              <a
                href={selectedProduct.product_url || `https://www.digikala.com/product/dkp-${selectedProduct.product_id}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-rose-400 hover:text-rose-300 font-semibold"
              >
                <span>مشاهده صفحه رسمی کالا در دیجی‌کالا</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>

              <button
                onClick={() => { setSelectedProduct(null); setProductDetail(null); }}
                className="px-4 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium cursor-pointer"
              >
                بستن
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
