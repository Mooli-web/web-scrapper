import React, { useState, useEffect } from 'react';
import { Layers, Folder, ChevronRight, Hash } from 'lucide-react';
import { fetchCategories } from '../api';

export default function CategoryExplorer() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCategories().then((res) => {
      setCategories(res);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-2">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white">کاوشگر شاخه‌های دیوار (Divar Categories)</h2>
            <p className="text-xs text-slate-400">دسته‌بندی‌های رسمی دیجیتال برای استخراج خودکار آگهی‌ها</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.map((c) => (
          <div key={c.category_key} className="glass-card rounded-2xl p-5 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-white text-sm">{c.title_fa}</span>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300">
                {c.post_count || 0} آگهی
              </span>
            </div>
            <div className="text-[11px] text-slate-400 space-y-1 font-mono">
              <p>اسلاگ: <span className="text-slate-200">{c.slug}</span></p>
              <p>کوئری سرچ: <span className="text-slate-200">{c.query_text}</span></p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
