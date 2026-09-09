import React, { useState, useEffect } from 'react';
import { TrendingDown, TrendingUp, Sparkles, Gavel, RefreshCw, ExternalLink, Filter, AlertTriangle } from 'lucide-react';
import { fetchEsamEvents } from '../api';
import ConditionBadge from '../components/ConditionBadge';
import PriceBadge from '../components/PriceBadge';

export default function Events() {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  // Filters
  const [eventType, setEventType] = useState('all');
  const [severity, setSeverity] = useState('all');

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchEsamEvents({
        event_type: eventType !== 'all' ? eventType : undefined,
        severity: severity !== 'all' ? severity : undefined,
        limit: 50
      });
      setEvents(res.events || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error(err);
      setEvents([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [eventType, severity]);

  const getEventBadge = (type) => {
    switch (type) {
      case 'PRICE_DROP':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <TrendingDown className="w-3.5 h-3.5" />
            کاهش قیمت
          </span>
        );
      case 'PRICE_HIKE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <TrendingUp className="w-3.5 h-3.5" />
            افزایش قیمت
          </span>
        );
      case 'NEW_BID':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            <Gavel className="w-3.5 h-3.5" />
            پیشنهاد جدید
          </span>
        );
      case 'NEW_LISTING':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            کالای جدید
          </span>
        );
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-black text-white">لاگ رویدادها و نوسانات بازار ایسام (Market Events)</h1>
          <p className="text-xs text-slate-400 mt-1">
            ثبت لحظه‌ای کالاهای جدید، ریزش‌های قیمتی و افزایش مبالغ پیشنهادی در مزایدات
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>بروزرسانی رویدادها</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              className="rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-200 focus:outline-none"
            >
              <option value="all">همه رویدادها</option>
              <option value="PRICE_DROP">کاهش قیمت‌ها</option>
              <option value="NEW_BID">پیشنهادهای جدید مزایده</option>
              <option value="NEW_LISTING">کالاهای جدید اضافه شده</option>
              <option value="PRICE_HIKE">افزایش قیمت‌ها</option>
            </select>
          </div>

          <div>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-200 focus:outline-none"
            >
              <option value="all">همه سطوح اهمیت</option>
              <option value="GOLDEN">فرصت‌های طلایی (GOLDEN)</option>
              <option value="WARNING">مهم (WARNING)</option>
              <option value="INFO">اطلاعاتی (INFO)</option>
            </select>
          </div>
        </div>

        <span className="text-xs text-slate-400 font-mono">
          تعداد کل رویدادها: <strong className="text-white">{Number(total).toLocaleString('fa-IR')}</strong>
        </span>
      </div>

      {/* Events Table */}
      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-bold uppercase">
              <tr>
                <th className="p-3.5">زمان وقوع</th>
                <th className="p-3.5">نوع رویداد</th>
                <th className="p-3.5">عنوان کالا</th>
                <th className="p-3.5">وضعیت سلامت</th>
                <th className="p-3.5">قیمت قبلی</th>
                <th className="p-3.5">قیمت جدید</th>
                <th className="p-3.5">میزان تغییر</th>
                <th className="p-3.5 text-center">مشاهده</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan="8" className="p-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2">
                      <RefreshCw className="w-6 h-6 animate-spin text-orange-400" />
                      <span>در حال دریافت لاگ‌های رویداد...</span>
                    </div>
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan="8" className="p-16 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-3">
                      <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-slate-600">
                        <TrendingDown className="w-8 h-8" />
                      </div>
                      <p className="text-sm font-bold text-slate-300">هنوز رویدادی ثبت نشده است</p>
                      <p className="text-xs text-slate-500 max-w-md">
                        به محض اینکه خزنده قیمت کالاها یا پیشنهادات مزایده را بررسی کند، تغییرات به شکل زنده در این جدول ثبت خواهد شد.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-800/40 transition">
                    <td className="p-3.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                      {ev.detected_at ? new Date(ev.detected_at).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                    </td>
                    <td className="p-3.5">
                      {getEventBadge(ev.event_type)}
                    </td>
                    <td className="p-3.5 max-w-xs font-bold text-slate-200 truncate" title={ev.title_fa}>
                      {ev.title_fa}
                    </td>
                    <td className="p-3.5">
                      <ConditionBadge condition={ev.condition} />
                    </td>
                    <td className="p-3.5 font-mono text-slate-400">
                      {ev.old_price_toman > 0 ? Number(ev.old_price_toman).toLocaleString('fa-IR') + ' ت' : '—'}
                    </td>
                    <td className="p-3.5 font-mono font-bold text-white">
                      {ev.new_price_toman > 0 ? Number(ev.new_price_toman).toLocaleString('fa-IR') + ' ت' : '—'}
                    </td>
                    <td className="p-3.5">
                      {ev.price_change_toman !== 0 ? (
                        <span className={`font-bold font-mono ${ev.price_change_toman < 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {ev.price_change_toman < 0 ? '' : '+'}{Number(ev.price_change_toman).toLocaleString('fa-IR')} ت
                          {ev.change_percent ? ` (${ev.change_percent}%)` : ''}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="p-3.5 text-center">
                      {ev.url && (
                        <a
                          href={ev.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex p-1.5 rounded-lg bg-slate-950 text-orange-400 hover:bg-orange-500/10 border border-slate-800"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
