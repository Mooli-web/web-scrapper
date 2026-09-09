import React, { useState, useEffect, useMemo } from 'react';
import { Layers, ChevronRight, ChevronDown, Package, Sparkles, ExternalLink, Search, Folder, FolderOpen, ArrowRight } from 'lucide-react';
import { fetchCategories } from '../api';

export default function CategoryExplorer({ onSelectCategory }) {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedKeys, setExpandedKeys] = useState(new Set(['electronic-devices', 'mobile-phone', 'laptops']));

  useEffect(() => {
    let active = true;
    const fetchCats = async () => {
      try {
        const data = await fetchCategories();
        if (active) setCategories(data);
      } catch (err) {
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchCats();
    return () => { active = false; };
  }, []);

  const toggleExpand = (key) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const tree = useMemo(() => {
    const map = {};
    const roots = [];

    categories.forEach((c) => {
      map[c.category_key] = { ...c, children: [] };
    });

    categories.forEach((c) => {
      if (c.parent_key && map[c.parent_key]) {
        map[c.parent_key].children.push(map[c.category_key]);
      } else if (!c.parent_key) {
        roots.push(map[c.category_key]);
      }
    });

    return roots;
  }, [categories]);

  const totalProducts = useMemo(() => {
    return categories.reduce((acc, c) => acc + (c.real_product_count || 0), 0);
  }, [categories]);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-indigo-950/60 via-slate-900/80 to-slate-900/90 border border-indigo-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white">کاوشگر درختی دسته‌بندی‌ها (Category Explorer)</h2>
            <p className="text-xs text-slate-400">
              مشاهده تعداد کالاهای واقعی ثبت‌شده در هر شاخه از بازار دیجیتال
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-2xl bg-slate-800/80 border border-slate-700 text-center">
            <span className="text-[10px] text-slate-400 block">دسته‌های تحت پایش</span>
            <span className="text-xs font-bold text-white">{categories.length} شاخه</span>
          </div>
          <div className="px-4 py-2 rounded-2xl bg-slate-800/80 border border-slate-700 text-center">
            <span className="text-[10px] text-slate-400 block">کل کالاهای ثبت‌شده</span>
            <span className="text-xs font-bold text-emerald-400">{totalProducts.toLocaleString('fa-IR')} کالا</span>
          </div>
        </div>
      </div>

      {/* Tree View Card */}
      <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-4">
        <h3 className="text-sm font-bold text-white mb-2">ساختار سلسله‌مراتبی دسته‌های الکترونیک:</h3>

        <div className="space-y-2">
          {tree.map((rootNode) => (
            <TreeNode
              key={rootNode.category_key}
              node={rootNode}
              expandedKeys={expandedKeys}
              onToggle={toggleExpand}
              onSelectCategory={onSelectCategory}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function TreeNode({ node, expandedKeys, onToggle, onSelectCategory }) {
  const isExpanded = expandedKeys.has(node.category_key);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-900/80 hover:bg-slate-800/60 border border-slate-800/80 transition group">
        <div className="flex items-center gap-2.5">
          {hasChildren ? (
            <button
              onClick={() => onToggle(node.category_key)}
              className="p-1 text-slate-400 hover:text-white cursor-pointer"
            >
              {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
          ) : (
            <span className="w-6" />
          )}

          {hasChildren ? (
            isExpanded ? <FolderOpen className="w-4 h-4 text-indigo-400" /> : <Folder className="w-4 h-4 text-slate-400" />
          ) : (
            <Package className="w-4 h-4 text-rose-400" />
          )}

          <div>
            <span className="font-bold text-xs text-white group-hover:text-rose-400 transition">
              {node.title_fa}
            </span>
            <span className="text-[10px] text-slate-500 font-mono mr-2">({node.category_key})</span>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="text-left">
            <span className="text-[10px] text-slate-400 block">تعداد کالا:</span>
            <strong className="text-white font-mono font-bold">
              {(node.real_product_count || 0).toLocaleString('fa-IR')}
            </strong>
          </div>

          <div className="text-left">
            <span className="text-[10px] text-slate-400 block">تخفیف‌ها:</span>
            <strong className="text-rose-400 font-mono font-bold">
              {(node.real_discount_count || 0).toLocaleString('fa-IR')}
            </strong>
          </div>

          {node.is_leaf && (
            <button
              onClick={() => onSelectCategory && onSelectCategory(node.category_key)}
              className="px-3 py-1 rounded-xl bg-rose-600/20 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/30 text-[11px] font-bold transition cursor-pointer"
            >
              مشاهده محصولات
            </button>
          )}
        </div>
      </div>

      {hasChildren && isExpanded && (
        <div className="pr-6 space-y-1 border-r border-slate-800 mr-3">
          {node.children.map((child) => (
            <TreeNode
              key={child.category_key}
              node={child}
              expandedKeys={expandedKeys}
              onToggle={onToggle}
              onSelectCategory={onSelectCategory}
            />
          ))}
        </div>
      )}
    </div>
  );
}
