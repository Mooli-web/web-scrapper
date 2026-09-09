import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, Radio, Terminal, Sparkles, CheckCircle2, AlertTriangle, Layers, Clock, Copy, Trash2, ArrowDown, Globe } from 'lucide-react';
import { startContinuousCrawler, stopContinuousCrawler } from '../api';

export default function LiveMissionControl({ onStatusChange }) {
  const [telemetry, setTelemetry] = useState({
    status: 'idle',
    active_store: 'دیجی‌کالا (digikala.com)',
    active_category: null,
    current_page: 0,
    total_pages: 0,
    products_scanned: 0,
    new_products_found: 0,
    price_changes_detected: 0,
    errors_count: 0,
    latest_log: 'موتور خزش دیجی‌کالا آماده است.'
  });

  const [logs, setLogs] = useState([]);
  const [lastLogId, setLastLogId] = useState(0);
  const [loadingAction, setLoadingAction] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef(null);

  useEffect(() => {
    let active = true;

    const streamInterval = setInterval(async () => {
      if (!active) return;
      try {
        const token = localStorage.getItem('auth_token');
        const res = await fetch(`/api/crawler/logs-stream?after_id=${lastLogId}`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (res.ok) {
          const data = await res.json();
          if (data.telemetry) setTelemetry(data.telemetry);
          if (data.new_logs && data.new_logs.length > 0) {
            setLogs((prev) => {
              const existing = new Set(prev.map((l) => l.id));
              const fresh = data.new_logs.filter((l) => !existing.has(l.id));
              return [...prev.slice(-200), ...fresh];
            });
            setLastLogId(data.latest_id);
          }
        }
      } catch (err) {}
    }, 1400);

    return () => {
      active = false;
      clearInterval(streamInterval);
    };
  }, [lastLogId]);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleStart = async () => {
    setLoadingAction(true);
    try {
      const data = await startContinuousCrawler();
      const localTime = new Date().toLocaleTimeString('fa-IR');
      setLogs((prev) => [...prev, { id: Date.now(), time: localTime, level: 'INFO', message: `🚀 ${data.message}` }]);
      if (onStatusChange) onStatusChange();
    } catch (err) {
      alert('خطا: ' + err);
    } finally {
      setLoadingAction(false);
    }
  };

  const handleStop = async () => {
    setLoadingAction(true);
    try {
      const data = await stopContinuousCrawler();
      const localTime = new Date().toLocaleTimeString('fa-IR');
      setLogs((prev) => [...prev, { id: Date.now(), time: localTime, level: 'WARNING', message: `⏹️ ${data.message}` }]);
    } catch (err) {
      alert('خطا: ' + err);
    } finally {
      setLoadingAction(false);
    }
  };

  const isRunning = telemetry.status === 'running';

  return (
    <div className="glass-card rounded-3xl p-6 border border-slate-800 space-y-5 bg-gradient-to-b from-slate-900/90 to-slate-950/90">
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center border shadow-lg ${
            isRunning 
              ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-emerald-500/20 animate-pulse'
              : 'bg-slate-800 text-slate-400 border-slate-700'
          }`}>
            <Radio className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-black text-white">مرکز فرماندهی پایش پیوسته بازار (Digikala Sweep)</h3>
              <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black border ${
                isRunning 
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}>
                {isRunning ? '🟢 در حال خزش ۲۴ ساعته' : '⚪ متوقف (Idle)'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              مصرف بهینه دیتابیس (In-Memory Delta Ledger) | شاخه فعال: <strong className="text-white">{telemetry.active_category || 'در انتظار'}</strong>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isRunning ? (
            <button
              onClick={handleStart}
              disabled={loadingAction}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white font-black text-xs shadow-lg shadow-emerald-600/30 transition cursor-pointer disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>شروع پایش پیوسته دیجی‌کالا</span>
            </button>
          ) : (
            <button
              onClick={handleStop}
              disabled={loadingAction}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs shadow-lg shadow-rose-600/30 transition cursor-pointer disabled:opacity-50"
            >
              <Square className="w-4 h-4 fill-white" />
              <span>توقف خزش</span>
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
        <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">کالاهای اسکن‌شده</span>
          <strong className="text-base font-black text-white font-mono">{Number(telemetry.products_scanned).toLocaleString('fa-IR')}</strong>
        </div>

        <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">کالاهای جدید کشف‌شده</span>
          <strong className="text-base font-black text-emerald-400 font-mono">{Number(telemetry.new_products_found).toLocaleString('fa-IR')}</strong>
        </div>

        <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">تغییرات قیمت</span>
          <strong className="text-base font-black text-rose-400 font-mono">{Number(telemetry.price_changes_detected).toLocaleString('fa-IR')}</strong>
        </div>

        <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800">
          <span className="text-[10px] text-slate-400 block">خطاهای ارتباطی</span>
          <strong className="text-sm font-black text-amber-400 font-mono">{telemetry.errors_count}</strong>
        </div>
      </div>

      <div className="rounded-2xl bg-slate-950 border border-slate-800 shadow-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/90 border-b border-slate-800 text-[11px] text-slate-400">
          <div className="flex items-center gap-2 font-mono">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span className="font-bold text-white">کنسول زنده فعالیت خط‌لوله (Live Log Stream):</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`px-2.5 py-1 rounded-lg border text-[10px] font-semibold transition cursor-pointer flex items-center gap-1 ${
                autoScroll ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              <ArrowDown className="w-3 h-3" />
              <span>{autoScroll ? 'اسکرول: روشن' : 'خاموش'}</span>
            </button>

            <button onClick={() => setLogs([])} className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 transition cursor-pointer">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div ref={logContainerRef} className="h-64 overflow-y-auto p-4 font-mono text-[11px] space-y-1.5 text-right select-text" dir="ltr">
          {logs.length > 0 ? (
            logs.map((logItem, i) => {
              const msg = typeof logItem === 'string' ? logItem : logItem.message;
              const time = typeof logItem === 'object' && logItem.time ? logItem.time : '';
              const isError = msg.includes('❌') || msg.includes('خطا');
              const isDrop = msg.includes('🔥') || msg.includes('تغییر');
              const isNew = msg.includes('جدید') || msg.includes('استخراج') || msg.includes('📄');
              const isPause = msg.includes('☕') || msg.includes('استراحت');

              const colorClass = isError ? 'text-rose-400 font-bold' : isDrop ? 'text-amber-300 font-semibold' : isNew ? 'text-emerald-300' : isPause ? 'text-sky-300' : 'text-slate-300';
              return (
                <div key={logItem.id || i} className={`leading-relaxed ${colorClass} break-words`}>
                  {time ? `[${time}] ` : ''}{msg}
                </div>
              );
            })
          ) : (
            <div className="text-slate-500 text-center py-20 font-sans text-xs">در انتظار شروع خزش دیجی‌کالا...</div>
          )}
        </div>
      </div>
    </div>
  );
}
