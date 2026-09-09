import React, { useState } from 'react';
import { X, Zap, RefreshCw, CheckCircle2, AlertTriangle, ExternalLink } from 'lucide-react';
import { testEsamProbe } from '../api';
import ConditionBadge from './ConditionBadge';
import PriceBadge from './PriceBadge';

export default function EsamTestModal({ isOpen, onClose }) {
  const [slug, setSlug] = useState('search/laptop?cc=40100');
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleTest = async () => {
    setLoading(true);
    try {
      const data = await testEsamProbe(slug, page);
      setResult(data);
    } catch (e) {
      setResult({ status: 'error', items_count: 0, error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <Zap className="w-5 h-5 text-orange-400" />
            <h3 className="text-base font-bold text-white">تست پروب زنده اسکرپر ایسام (Live Probe)</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="py-5 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-slate-300 mb-1">مسیر هدف (Slug / Query)</label>
              <select
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 p-2.5 text-xs text-slate-200"
              >
                <option value="search/laptop?cc=40100">لپ‌تاپ و نوت‌بوک (cc=40100)</option>
                <option value="auctions?activeTab=TowardTheEnd">مزایدات رو به پایان (Auctions Ending)</option>
                <option value="auctions?activeTab=HasBid">مزایدات دارای پیشنهاد (Auctions Has Bid)</option>
                <option value="search/graphic-card?cc=40201">کارت گرافیک (cc=40201)</option>
                <option value="search/playstation?cc=50100">پلی‌استیشن (cc=50100)</option>
                <option value="search/apple-iphone?cc=30101">آیفون اپل (cc=30101)</option>
                <option value="search/vintage-mobile?cc=93401">گوشی‌های عتیقه نوستالژیک</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">شماره صفحه</label>
              <input
                type="number"
                min="1"
                max="10"
                value={page}
                onChange={(e) => setPage(parseInt(e.target.value) || 1)}
                className="w-full rounded-xl bg-slate-950 border border-slate-800 p-2.5 text-xs text-slate-200"
              />
            </div>
          </div>

          <button
            onClick={handleTest}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-bold transition disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            <span>اجرای پروب استخراج زنده</span>
          </button>

          {result && (
            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-400">
                  وضعیت:{' '}
                  <span className={result.items_count > 0 ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                    {result.status}
                  </span>
                </span>
                <span className="text-slate-400">
                  تعداد استخراج‌شده: <span className="text-white font-bold">{result.items_count} کالا</span>
                </span>
                {result.elapsed_ms && (
                  <span className="text-slate-400 font-mono">زمان: {result.elapsed_ms}ms</span>
                )}
              </div>

              {result.sample_items && result.sample_items.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-slate-300">نمونه کالاهای استخراج‌شده:</p>
                  {result.sample_items.map((item, idx) => (
                    <div key={idx} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-3 min-w-0">
                        {item.image_url && (
                          <img src={item.image_url} alt="" className="w-10 h-10 object-cover rounded-lg bg-slate-900 border border-slate-800 shrink-0" />
                        )}
                        <div className="truncate">
                          <p className="font-bold text-slate-200 truncate">{item.title_fa}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <ConditionBadge condition={item.condition} />
                            {item.is_auction && (
                              <span className="text-[10px] text-amber-400 font-semibold">
                                مزایده ({item.bids_count || 0} پیشنهاد)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="text-left shrink-0">
                        <PriceBadge price={item.selling_price_toman} isAuction={item.is_auction} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end pt-3 border-t border-slate-800">
          <button onClick={onClose} className="px-4 py-1.5 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700">
            بستن
          </button>
        </div>
      </div>
    </div>
  );
}
