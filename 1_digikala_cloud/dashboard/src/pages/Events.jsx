import React, { useState, useEffect, useMemo } from 'react';
import { Flame, ExternalLink, PackageX, ArrowUpDown, ArrowUp, ArrowDown, Search } from 'lucide-react';
import SeverityBadge from '../components/SeverityBadge';
import { fetchEvents, formatToman, formatPercent, formatPersianDate } from '../api';

export default function Events() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc'); // 'asc' or 'desc'

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchEvents({
      severity: severityFilter !== 'all' ? severityFilter : undefined
    }).then((res) => {
      if (active) {
        setEvents(res || []);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [severityFilter]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const sortedEvents = useMemo(() => {
    let filtered = [...events];
    if (search.trim()) {
      const s = search.trim().toLowerCase();
      filtered = filtered.filter(
        (e) => (e.title_fa || '').toLowerCase().includes(s) || (e.brand || '').toLowerCase().includes(s)
      );
    }

    filtered.sort((a, b) => {
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

    return filtered;
  }, [events, search, sortField, sortOrder]);

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
      {/* Header */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-amber-950/60 via-slate-900/80 to-slate-900/90 border border-amber-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
            <Flame className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white">دفترکل رویدادهای افت قیمت و تخفیف‌ها (Price Drops)</h2>
            <p className="text-xs text-slate-400">ثبت لحظه‌ای ریزش قیمت‌ها با امکان مرتب‌سازی چندستونه</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute right-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="جستجو در رویدادها..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-xl pr-8 pl-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 transition"
            />
          </div>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-500 transition font-medium"
          >
            <option value="all">همه شدت‌ها</option>
            <option value="high">🔥 فقط افت‌های شدید (بالای ۱۵٪)</option>
            <option value="medium">افت‌های متوسط (۸ تا ۱۵٪)</option>
            <option value="low">افت‌های جزئی (زیر ۸٪)</option>
          </select>
        </div>
      </div>

      {/* Events Table */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800">
        {loading ? (
          <div className="py-20 text-center space-y-2">
            <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400">در حال دریافت رویدادهای افت قیمت...</p>
          </div>
        ) : sortedEvents.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-bold select-none">
                  <th className="pb-3 pr-2 cursor-pointer hover:text-white" onClick={() => handleSort('title_fa')}>
                    <div className="flex items-center gap-1">
                      <span>کالا و مشخصات</span>
                      {renderSortIcon('title_fa')}
                    </div>
                  </th>
                  <th className="pb-3 text-center">نوع رویداد</th>
                  <th className="pb-3 cursor-pointer hover:text-white" onClick={() => handleSort('old_price_toman')}>
                    <div className="flex items-center gap-1">
                      <span>قیمت قبلی</span>
                      {renderSortIcon('old_price_toman')}
                    </div>
                  </th>
                  <th className="pb-3 cursor-pointer hover:text-white" onClick={() => handleSort('new_price_toman')}>
                    <div className="flex items-center gap-1">
                      <span>قیمت جدید</span>
                      {renderSortIcon('new_price_toman')}
                    </div>
                  </th>
                  <th className="pb-3 cursor-pointer hover:text-white" onClick={() => handleSort('drop_percent')}>
                    <div className="flex items-center gap-1">
                      <span>درصد افت</span>
                      {renderSortIcon('drop_percent')}
                    </div>
                  </th>
                  <th className="pb-3 cursor-pointer hover:text-white" onClick={() => handleSort('severity')}>
                    <div className="flex items-center gap-1">
                      <span>شدت افت</span>
                      {renderSortIcon('severity')}
                    </div>
                  </th>
                  <th className="pb-3 cursor-pointer hover:text-white" onClick={() => handleSort('created_at')}>
                    <div className="flex items-center gap-1">
                      <span>زمان ثبت</span>
                      {renderSortIcon('created_at')}
                    </div>
                  </th>
                  <th className="pb-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {sortedEvents.map((evt) => {
                  const targetUrl = evt.product_url || `https://www.digikala.com/product/dkp-${evt.product_id}/`;
                  return (
                    <tr key={evt.id} className="hover:bg-slate-900/60 transition group">
                      <td className="py-3.5 pr-2 max-w-[280px]">
                        <a
                          href={targetUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-bold text-white block truncate group-hover:text-amber-400 transition"
                          title={evt.title_fa}
                        >
                          {evt.title_fa}
                        </a>
                        <span className="text-[10px] text-slate-400">{evt.brand} | {evt.category_name || 'کالای دیجیتال'}</span>
                      </td>
                      <td className="py-3.5 text-center">
                        <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-semibold">
                          📉 افت قیمت
                        </span>
                      </td>
                      <td className="py-3.5 line-through text-slate-500 font-mono font-medium">
                        {formatToman(evt.old_price_toman)}
                      </td>
                      <td className="py-3.5 font-bold text-emerald-400 font-mono text-sm">
                        {formatToman(evt.new_price_toman)}
                      </td>
                      <td className="py-3.5">
                        <span className="px-2 py-0.5 rounded-lg bg-rose-500/20 text-rose-400 text-[11px] font-black font-mono border border-rose-500/30">
                          {formatPercent(evt.drop_percent)}
                        </span>
                      </td>
                      <td className="py-3.5">
                        <SeverityBadge severity={evt.severity} />
                      </td>
                      <td className="py-3.5 text-[10px] text-slate-400">
                        {formatPersianDate(evt.created_at)}
                      </td>
                      <td className="py-3.5 text-center">
                        <a
                          href={targetUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-rose-600/20 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/30 text-[11px] font-bold transition"
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
            <PackageX className="w-12 h-12 text-slate-600 mx-auto" />
            <h4 className="text-sm font-bold text-white">رویدادی با این مشخصات یافت نشد</h4>
            <p className="text-xs text-slate-400">با پایش پیوسته بازار، به محض کاهش قیمت هر کالا، رویداد آن ثبت می‌شود.</p>
          </div>
        )}
      </div>
    </div>
  );
}
