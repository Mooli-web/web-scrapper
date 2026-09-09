import React, { useState, useEffect } from 'react';
import { Gavel, Clock, Flame, RefreshCw, ExternalLink, ShieldCheck, AlertCircle } from 'lucide-react';
import { fetchActiveAuctions } from '../api';
import ConditionBadge from '../components/ConditionBadge';
import PriceBadge from '../components/PriceBadge';

export default function Auctions() {
  const [auctions, setAuctions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await fetchActiveAuctions({ limit: 50 });
      setAuctions(res.auctions || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error(err);
      setAuctions([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-black text-white">دیده‌بان مزایدات داغ و رو به پایان ایسام (Hot Auctions Watcher)</h1>
            <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/40 animate-pulse">
              <Flame className="w-3.5 h-3.5 text-orange-400" />
              لحظه‌ای
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            رصد زنده مزایداتی که مهلت آن‌ها رو به اتمام است یا حجم پیشنهاد بالایی دریافت کرده‌اند
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 hover:text-white hover:border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>بروزرسانی مزایدات</span>
        </button>
      </div>

      {/* Grid of Auction Cards */}
      {loading && auctions.length === 0 ? (
        <div className="p-16 text-center text-slate-400 rounded-2xl bg-slate-900/40 border border-slate-800">
          <RefreshCw className="w-8 h-8 animate-spin text-orange-400 mx-auto mb-3" />
          <p className="text-sm font-bold text-slate-200">در حال دریافت مزایدات فعال ایسام...</p>
        </div>
      ) : auctions.length === 0 ? (
        <div className="p-16 text-center text-slate-400 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-slate-600 w-16 h-16 mx-auto flex items-center justify-center mb-3">
            <Gavel className="w-8 h-8" />
          </div>
          <p className="text-sm font-bold text-slate-200 mb-1">هنوز هیچ مزایده‌ای در پایگاه داده ثبت نشده است</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            با زدن دکمه «شروع خزش پیوسته ایسام» در بالای داشبورد، فید مزایدات رو به پایان و دارای پیشنهاد به سرعت پایش و اینجا لیست می‌شود.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {auctions.map((item) => (
            <div
              key={item.id || item.item_id}
              className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm shadow-lg hover:border-orange-500/40 transition flex flex-col justify-between"
            >
              <div>
                {/* Header: Condition & Countdown */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <ConditionBadge condition={item.condition} />
                  {item.time_remaining ? (
                    <span className="inline-flex items-center gap-1 text-xs font-mono font-bold text-rose-400 bg-rose-950/40 border border-rose-500/30 px-2 py-0.5 rounded-md" dir="ltr">
                      <Clock className="w-3.5 h-3.5" />
                      {item.time_remaining}
                    </span>
                  ) : (
                    <span className="text-[11px] text-slate-500">مزایده فعال</span>
                  )}
                </div>

                {/* Image + Title */}
                <div className="flex gap-3 mb-3">
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt=""
                      className="w-16 h-16 object-cover rounded-xl bg-slate-950 border border-slate-800 shrink-0"
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                  )}
                  <div>
                    <h3 className="text-xs font-bold text-slate-100 line-clamp-2 leading-relaxed" title={item.title_fa}>
                      {item.title_fa}
                    </h3>
                    <p className="text-[10px] text-slate-400 mt-1">
                      دسته‌بندی: {item.category_name_fa || 'کالای دیجیتال'}
                    </p>
                  </div>
                </div>

                {/* Bid Stats */}
                <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">بالاترین پیشنهاد:</span>
                    <PriceBadge price={item.selling_price_toman} isAuction={true} />
                  </div>

                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">قیمت پایه:</span>
                    <span className="text-slate-300 font-mono">
                      {item.base_price_toman ? Number(item.base_price_toman).toLocaleString('fa-IR') + ' تومان' : 'نامشخص'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-800/60">
                    <span className="text-slate-400">تعداد پیشنهادات:</span>
                    <span className="font-bold text-amber-400">
                      {Number(item.bids_count || 0).toLocaleString('fa-IR')} پیشنهاد
                    </span>
                  </div>
                </div>
              </div>

              {/* Footer: Seller + Action */}
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-[11px] text-slate-400 truncate max-w-[140px]">
                  {item.seller_name || 'فروشنده ایسام'}
                </span>

                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 text-white text-xs font-bold shadow-sm hover:from-orange-500 hover:to-amber-500 transition"
                >
                  <span>ثبت پیشنهاد در ایسام</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
