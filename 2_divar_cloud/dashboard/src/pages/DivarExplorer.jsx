import React, { useState, useEffect, useMemo } from 'react';
import { Smartphone, Search, ExternalLink, MapPin, Clock, Sparkles, Filter, PackageX, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { fetchPosts, formatToman, formatPersianDate } from '../api';

export default function DivarExplorer() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [condition, setCondition] = useState('all');
  const [sortField, setSortField] = useState('last_seen_at');
  const [sortOrder, setSortOrder] = useState('desc'); // 'asc' or 'desc'
  const [page, setPage] = useState(1);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchPosts({
      search: search.trim() || undefined,
      category: category !== 'all' ? category : undefined,
      condition: condition !== 'all' ? condition : undefined,
      page,
      page_size: 20
    }).then((res) => {
      if (active) {
        setData(res || { items: [], total: 0, page: 1, total_pages: 1 });
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [search, category, condition, page]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const sortedItems = useMemo(() => {
    const list = [...(data.items || [])];
    list.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = (bVal || '').toLowerCase();
        return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }

      aVal = Number(aVal || 0);
      bVal = Number(bVal || 0);
      return sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
    });
    return list;
  }, [data.items, sortField, sortOrder]);

  const renderSortIcon = (field) => {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3 text-slate-500 opacity-60" />;
    return sortOrder === 'asc' ? (
      <ArrowUp className="w-3 h-3 text-rose-400 font-bold" />
    ) : (
      <ArrowDown className="w-3 h-3 text-rose-400 font-bold" />
    );
  };

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 shadow-lg shadow-rose-500/10">
              <Smartphone className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-black text-white">دفترکل آگهی‌های دیوار (Divar Ads Ledger)</h2>
              <p className="text-xs text-slate-400 mt-0.5">پایش لحظه‌ای آگهی‌های کارکرده و استوک با امکان مرتب‌سازی چندستونه</p>
            </div>
          </div>
          <span className="text-xs font-bold px-3 py-1.5 rounded-xl bg-slate-950 text-rose-400 border border-slate-800">
            مجموع: {data.total.toLocaleString('fa-IR')} آگهی ثبت‌شده
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div className="relative">
            <Search className="w-4 h-4 absolute right-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="جستجو در عنوان، برند یا محله..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl pr-9 pl-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 transition"
            />
          </div>

          <div>
            <select
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500 transition font-medium"
            >
              <option value="all">همه شاخه‌ها</option>
              <option value="mobile-apple">گوشی‌های اپل (iPhone)</option>
              <option value="mobile-samsung">گوشی‌های سامسونگ (Galaxy)</option>
              <option value="mobile-xiaomi">گوشی‌های شیائومی (Poco/Redmi)</option>
              <option value="laptops-gaming">لپ‌تاپ‌های گیمینگ</option>
              <option value="laptops-apple">مک‌بوک‌های اپل</option>
              <option value="gaming-consoles">کنسول‌های بازی</option>
              <option value="graphic-cards">کارت گرافیک</option>
              <option value="processors">پردازنده و مادربورد</option>
              <option value="smart-watches">ساعت هوشمند</option>
              <option value="headphones">هدفون و هندزفری</option>
              <option value="tablets">تبلت و آیپد</option>
            </select>
          </div>

          <div>
            <select
              value={condition}
              onChange={(e) => { setCondition(e.target.value); setPage(1); }}
              className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500 transition font-medium"
            >
              <option value="all">همه وضعیت‌ها</option>
              <option value="در حد نو">در حد نو</option>
              <option value="نو (پلمپ/آکبند)">نو (پلمپ/آکبند)</option>
              <option value="استوک گرید A">استوک گرید A</option>
              <option value="کارکرده">کارکرده</option>
            </select>
          </div>
        </div>
      </div>

      <div className="glass-card rounded-3xl p-6 border border-slate-800">
        {loading ? (
          <div className="py-20 text-center space-y-2">
            <div className="w-8 h-8 border-2 border-rose-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400">در حال بارگذاری آگهی‌ها...</p>
          </div>
        ) : sortedItems.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-bold select-none">
                  <th className="pb-3 pr-2 cursor-pointer hover:text-white" onClick={() => handleSort('title_fa')}>
                    <div className="flex items-center gap-1">
                      <span>عنوان و تصویر آگهی</span>
                      {renderSortIcon('title_fa')}
                    </div>
                  </th>
                  <th className="pb-3 text-center cursor-pointer hover:text-white" onClick={() => handleSort('condition')}>
                    <div className="flex items-center justify-center gap-1">
                      <span>وضعیت کالا</span>
                      {renderSortIcon('condition')}
                    </div>
                  </th>
                  <th className="pb-3 cursor-pointer hover:text-white" onClick={() => handleSort('selling_price_toman')}>
                    <div className="flex items-center gap-1">
                      <span>قیمت پیشنهادی</span>
                      {renderSortIcon('selling_price_toman')}
                    </div>
                  </th>
                  <th className="pb-3 text-center cursor-pointer hover:text-white" onClick={() => handleSort('category_name')}>
                    <div className="flex items-center justify-center gap-1">
                      <span>شاخه کالا</span>
                      {renderSortIcon('category_name')}
                    </div>
                  </th>
                  <th className="pb-3 text-center cursor-pointer hover:text-white" onClick={() => handleSort('district')}>
                    <div className="flex items-center justify-center gap-1">
                      <span>موقعیت / محله</span>
                      {renderSortIcon('district')}
                    </div>
                  </th>
                  <th className="pb-3 text-center cursor-pointer hover:text-white" onClick={() => handleSort('last_seen_at')}>
                    <div className="flex items-center justify-center gap-1">
                      <span>زمان ثبت</span>
                      {renderSortIcon('last_seen_at')}
                    </div>
                  </th>
                  <th className="pb-3 text-center">لینک مستقیم</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {sortedItems.map((post) => {
                  const isLikeNew = post.condition && post.condition.includes('در حد');
                  const isNew = post.condition && post.condition.includes('نو');
                  const condBadge = isLikeNew 
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                    : isNew 
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    : 'bg-slate-800 text-slate-300 border-slate-700';

                  return (
                    <tr key={post.token} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 pr-1">
                        <div className="flex items-center gap-3">
                          {post.image_url ? (
                            <img src={post.image_url} alt={post.title_fa} className="w-11 h-11 rounded-xl object-cover bg-white/5 border border-slate-800 shrink-0" onError={(e) => { e.target.style.display = 'none'; }} />
                          ) : (
                            <div className="w-11 h-11 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500 shrink-0">📱</div>
                          )}
                          <div className="space-y-0.5 max-w-md">
                            <a href={post.post_url} target="_blank" rel="noopener noreferrer" className="font-bold text-white hover:text-rose-400 transition line-clamp-2 block" title={post.title_fa}>
                              {post.title_fa}
                            </a>
                            <span className="text-[10px] text-slate-400 font-semibold">{post.brand || 'متفرقه'}</span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 text-center">
                        <span className={`px-2 py-0.5 rounded-lg text-[10px] font-bold border ${condBadge}`}>
                          {post.condition || 'کارکرده'}
                        </span>
                      </td>

                      <td className="py-3.5">
                        <span className="font-mono font-bold text-emerald-400 text-sm block">
                          {formatToman(post.selling_price_toman)}
                        </span>
                      </td>

                      <td className="py-3.5 text-center">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {post.category_name || 'دیجیتال'}
                        </span>
                      </td>

                      <td className="py-3.5 text-center text-slate-300 text-xs">
                        {post.district || post.city}
                      </td>

                      <td className="py-3.5 text-center text-slate-400 text-[10px]">
                        {formatPersianDate(post.last_seen_at)}
                      </td>

                      <td className="py-3.5 text-center">
                        <a href={post.post_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1 rounded-lg bg-rose-600/20 hover:bg-rose-600 text-rose-300 hover:text-white border border-rose-500/30 text-[10px] font-bold transition">
                          مشاهده
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
            <PackageX className="w-12 h-12 text-slate-600 mx-auto" />
            <h4 className="text-sm font-bold text-white">آگهی یافت نشد</h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto">با شروع پایش ۲۴ ساعته، آگهی‌ها به صورت زنده استخراج و ثبت می‌شوند.</p>
          </div>
        )}

        {data.total_pages > 1 && (
          <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-800 text-xs text-slate-400">
            <span>صفحه {page} از {data.total_pages} (مجموع {data.total} آگهی)</span>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition cursor-pointer">صفحه قبلی</button>
              <button disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 transition cursor-pointer">صفحه بعدی</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
