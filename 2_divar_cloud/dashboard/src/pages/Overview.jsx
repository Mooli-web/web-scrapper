import React, { useState, useEffect } from 'react';
import { Smartphone, Flame, Activity, Sparkles, ExternalLink, Package, CheckCircle2 } from 'lucide-react';
import StatCard from '../components/StatCard';
import LiveMissionControl from '../components/LiveMissionControl';
import { fetchOverview, formatToman, formatPersianDate } from '../api';

export default function Overview({ onNavigateToPosts }) {
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
      <LiveMissionControl onStatusChange={handleRefresh} />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="کل آگهی‌های دیجیتال دیوار"
          value={data ? Number(data.total_posts).toLocaleString('fa-IR') : '۰'}
          subtitle={`کالای نو / پلمپ: ${data ? Number(data.brand_new_count).toLocaleString('fa-IR') : '۰'}`}
          icon={Smartphone}
          color="rose"
          trend={{ positive: true, text: 'استخراج ۲۴/۷', label: 'دیوار' }}
        />
        <StatCard
          title="کالاهای در حد نو"
          value={data ? Number(data.like_new_count).toLocaleString('fa-IR') : '۰'}
          subtitle={`فرصت‌های خرید بهینه`}
          icon={Sparkles}
          color="amber"
          trend={{ positive: true, text: 'کیفیت عالی', label: 'در حد نو' }}
        />
        <StatCard
          title="میانگین قیمت آگهی‌ها"
          value={data ? formatToman(data.avg_price) : '۰ تومان'}
          subtitle={`کف قیمت بازار دست‌دوم`}
          icon={Activity}
          color="emerald"
          trend={{ positive: true, text: 'بازار نقد', label: 'میانگین' }}
        />
        <StatCard
          title="نوسانات ۲۴ ساعت اخیر"
          value={data ? Number(data.events_24h).toLocaleString('fa-IR') : '۰'}
          subtitle={`افت قیمت فروشندگان`}
          icon={Flame}
          color="sky"
          trend={{ positive: true, text: 'تغییر قیمت', label: 'دفترکل' }}
        />
      </div>

      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-bold text-white">آخرین آگهی‌های ثبت‌شده در دیتابیس دیوار</h3>
          </div>
          <button onClick={onNavigateToPosts} className="text-xs text-rose-400 hover:text-rose-300 font-bold">مشاهده تمام آگهی‌ها</button>
        </div>

        {data?.recent_ads && data.recent_ads.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.recent_ads.map((ad) => (
              <div key={ad.token} className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-rose-500/40 transition flex flex-col justify-between gap-3 group">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[10px] font-black">
                      {ad.condition}
                    </span>
                    <span className="text-[10px] text-slate-400">{ad.brand}</span>
                  </div>
                  <a href={ad.post_url} target="_blank" rel="noopener noreferrer" className="text-xs font-bold text-white group-hover:text-rose-400 transition line-clamp-2 block">
                    {ad.title_fa}
                  </a>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-emerald-400 block">{formatToman(ad.selling_price_toman)}</span>
                    <span className="text-[10px] text-slate-500">{ad.district || 'تهران'}</span>
                  </div>

                  <a href={ad.post_url} target="_blank" rel="noopener noreferrer" className="px-3 py-1 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-bold flex items-center gap-1 transition">
                    <span>دیوار</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10 space-y-2">
            <p className="text-xs text-slate-400">هنوز آگهی در دیتابیس ثبت نشده است.</p>
            <p className="text-[11px] text-slate-500">برای استخراج زنده آگهی‌ها، دکمه «شروع پایش ۲۴ ساعته دیوار» را بزنید.</p>
          </div>
        )}
      </div>
    </div>
  );
}
