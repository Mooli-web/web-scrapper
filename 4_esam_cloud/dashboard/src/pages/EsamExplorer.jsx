import React, { useState, useEffect } from 'react';
import { Search, Filter, ArrowUpDown, ArrowUp, ArrowDown, ExternalLink, RefreshCw, ShoppingBag, Eye, Clock, Gavel, Image as ImageIcon } from 'lucide-react';
import { fetchEsamItems, fetchEsamCategories } from '../api';
import ConditionBadge from '../components/ConditionBadge';
import PriceBadge from '../components/PriceBadge';
import AuctionBadge from '../components/AuctionBadge';

export default function EsamExplorer() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [categories, setCategories] = useState([]);

  // Filter States
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [condition, setCondition] = useState('all');
  const [auctionOnly, setAuctionOnly] = useState(false);

  // Sorting
  const [sortBy, setSortBy] = useState('last_seen_at');
  const [sortOrder, setSortOrder] = useState('desc');

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 25;

  const loadCategories = async () => {
    try {
      const res = await fetchEsamCategories();
      setCategories(res.categories || []);
    } catch {}
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchEsamItems({
        search: search.trim() || undefined,
        category: category !== 'all' ? category : undefined,
        condition: condition !== 'all' ? condition : undefined,
        auction_only: auctionOnly || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: pageSize,
        offset: (page - 1) * pageSize
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error(err);
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    loadData();
  }, [category, condition, auctionOnly, sortBy, sortOrder, page]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    loadData();
  };

  const toggleSort = (column) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const getSortIcon = (column) => {
    if (sortBy !== column) return <ArrowUpDown className="w-3.5 h-3.5 text-slate-500 opacity-40 group-hover:opacity-100 transition" />;
    return sortOrder === 'asc' 
      ? <ArrowUp className="w-3.5 h-3.5 text-orange-400 font-bold" />
      : <ArrowDown className="w-3.5 h-3.5 text-orange-400 font-bold" />;
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-5">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-white">دفتر کل اقلام و کالاهای ایسام (Esam Items Ledger)</h1>
          <p className="text-xs text-slate-400 mt-1">
            جدول تعاملی و مرتب‌سازی چندستونه کالاهای نو، دست‌دوم، استوک و مزایدات فعال ایسام
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>بروزرسانی جدول</span>
        </button>
      </div>

      {/* Filters Bar */}
      <div className="p-4 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} className="relative md:col-span-2">
            <Search className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو در عنوان کالا، فروشنده، برند..."
              className="w-full rounded-xl bg-slate-950 border border-slate-800 pr-9 pl-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500/50"
            />
          </form>

          {/* Category Filter */}
          <div>
            <select
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50"
            >
              <option value="all">همه دسته‌بندی‌ها</option>
              {categories.map((cat) => (
                <option key={cat.id || cat.category_key} value={cat.category_key}>
                  {cat.title_fa} ({cat.real_items_count || 0})
                </option>
              ))}
            </select>
          </div>

          {/* Condition Filter */}
          <div>
            <select
              value={condition}
              onChange={(e) => { setCondition(e.target.value); setPage(1); }}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50"
            >
              <option value="all">همه وضعیت‌ها</option>
              <option value="نو (پلمپ/آکبند)">نو (پلمپ / آکبند)</option>
              <option value="در حد نو">در حد نو</option>
              <option value="استوک گرید A">استوک گرید A</option>
              <option value="دست دوم">دست دوم</option>
              <option value="معیوب / جهت قطعات">معیوب / جهت قطعات</option>
            </select>
          </div>
        </div>

        {/* Second Row: Toggles */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/80">
          <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-300">
            <input
              type="checkbox"
              checked={auctionOnly}
              onChange={(e) => { setAuctionOnly(e.target.checked); setPage(1); }}
              className="w-4 h-4 rounded bg-slate-950 border-slate-800 text-orange-500 focus:ring-0"
            />
            <span className="flex items-center gap-1.5 text-amber-400">
              <Gavel className="w-3.5 h-3.5" />
              فقط مزایدات نمایش داده شوند
            </span>
          </label>

          <span className="text-xs text-slate-400 font-mono">
            تعداد کل نتایج: <strong className="text-white">{Number(total).toLocaleString('fa-IR')}</strong> کالا
          </span>
        </div>
      </div>

      {/* Items Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-bold uppercase">
              <tr>
                <th className="p-3.5">تصویر</th>
                <th className="p-3.5 cursor-pointer select-none group" onClick={() => toggleSort('title_fa')}>
                  <div className="flex items-center gap-1.5">
                    <span>عنوان و دسته‌بندی کالا</span>
                    {getSortIcon('title_fa')}
                  </div>
                </th>
                <th className="p-3.5 cursor-pointer select-none group" onClick={() => toggleSort('condition')}>
                  <div className="flex items-center gap-1.5">
                    <span>وضعیت سلامت</span>
                    {getSortIcon('condition')}
                  </div>
                </th>
                <th className="p-3.5">نوع معامله</th>
                <th className="p-3.5 cursor-pointer select-none group" onClick={() => toggleSort('selling_price_toman')}>
                  <div className="flex items-center gap-1.5">
                    <span>قیمت فروش / بالاترین پیشنهاد</span>
                    {getSortIcon('selling_price_toman')}
                  </div>
                </th>
                <th className="p-3.5 cursor-pointer select-none group" onClick={() => toggleSort('bids_count')}>
                  <div className="flex items-center gap-1.5">
                    <span>پیشنهادها</span>
                    {getSortIcon('bids_count')}
                  </div>
                </th>
                <th className="p-3.5">فروشنده</th>
                <th className="p-3.5 cursor-pointer select-none group" onClick={() => toggleSort('last_seen_at')}>
                  <div className="flex items-center gap-1.5">
                    <span>آخرین مشاهده</span>
                    {getSortIcon('last_seen_at')}
                  </div>
                </th>
                <th className="p-3.5 text-center">لینک مستقیم</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan="9" className="p-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2">
                      <RefreshCw className="w-6 h-6 animate-spin text-orange-400" />
                      <span>در حال دریافت و رندر داده‌های ایسام...</span>
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan="9" className="p-16 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-3">
                      <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-slate-600">
                        <ShoppingBag className="w-8 h-8" />
                      </div>
                      <p className="text-sm font-bold text-slate-300">هیچ کالایی مطابق با فیلترها یافت نشد</p>
                      <p className="text-xs text-slate-500 max-w-md">
                        برای شروع جمع‌آوری کالاها، از بالای صفحه دکمه «شروع خزش پیوسته ایسام» را بزنید یا فیلترهای جستجو را بازنشانی کنید.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id || item.item_id} className="hover:bg-slate-800/40 transition">
                    {/* Image */}
                    <td className="p-3.5">
                      {item.image_url ? (
                        <img
                          src={item.image_url}
                          alt=""
                          className="w-12 h-12 object-cover rounded-xl bg-slate-950 border border-slate-800 shrink-0"
                          onError={(e) => { e.target.style.display = 'none'; }}
                        />
                      ) : (
                        <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-600">
                          <ImageIcon className="w-5 h-5" />
                        </div>
                      )}
                    </td>

                    {/* Title & Category */}
                    <td className="p-3.5 max-w-xs">
                      <p className="font-bold text-slate-200 text-xs leading-relaxed line-clamp-2" title={item.title_fa}>
                        {item.title_fa}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                          {item.category_name_fa || item.category_key}
                        </span>
                        {item.brand && (
                          <span className="text-[10px] text-slate-400">{item.brand}</span>
                        )}
                      </div>
                    </td>

                    {/* Condition */}
                    <td className="p-3.5">
                      <ConditionBadge condition={item.condition} />
                    </td>

                    {/* Auction Status */}
                    <td className="p-3.5">
                      <AuctionBadge isAuction={item.is_auction} timeRemaining={item.time_remaining} bidsCount={item.bids_count} />
                    </td>

                    {/* Price */}
                    <td className="p-3.5">
                      <PriceBadge price={item.selling_price_toman} isAuction={item.is_auction} bidsCount={item.bids_count} />
                    </td>

                    {/* Bids */}
                    <td className="p-3.5 font-mono">
                      {item.is_auction ? (
                        <span className="text-amber-400 font-bold">
                          {Number(item.bids_count || 0).toLocaleString('fa-IR')}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>

                    {/* Seller */}
                    <td className="p-3.5 text-slate-300">
                      <p className="font-semibold text-[11px] truncate max-w-[120px]">{item.seller_name || 'فروشنده ایسام'}</p>
                      {item.seller_city && <p className="text-[10px] text-slate-500">{item.seller_city}</p>}
                    </td>

                    {/* Last Seen */}
                    <td className="p-3.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                      {item.last_seen_at ? new Date(item.last_seen_at).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' }) : '—'}
                    </td>

                    {/* External Link */}
                    <td className="p-3.5 text-center">
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 p-2 rounded-lg bg-slate-950 text-orange-400 border border-slate-800 hover:border-orange-500/50 hover:bg-orange-500/10 transition"
                        title="مشاهده آگهی در ایسام"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-slate-800 bg-slate-950/60 text-xs">
            <span className="text-slate-400">
              صفحه <strong className="text-white">{page}</strong> از <strong className="text-white">{totalPages}</strong>
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded-lg bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 transition"
              >
                صفحه قبل
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 rounded-lg bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 transition"
              >
                صفحه بعد
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
