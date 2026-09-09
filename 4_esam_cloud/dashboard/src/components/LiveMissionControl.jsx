import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, Radio, Terminal, Sparkles, CheckCircle2, AlertTriangle, Layers, Clock, Copy, Trash2, ArrowDown, ShoppingBag } from 'lucide-react';
import { startEsamCrawler, stopEsamCrawler, fetchCrawlerLogsStream } from '../api';

export default function LiveMissionControl({ onStatusChange }) {
  const [telemetry, setTelemetry] = useState({
    status: 'idle',
    active_category: null,
    current_page: 0,
    total_pages: 0,
    items_scanned: 0,
    new_items_found: 0,
    price_changes_detected: 0,
    bids_updated: 0,
    errors_count: 0,
    latest_log: 'موتور مستقل خزش ایسام آماده به کار است.'
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
        const data = await fetchCrawlerLogsStream(lastLogId);
        if (data.telemetry) setTelemetry(data.telemetry);
        if (data.new_logs && data.new_logs.length > 0) {
          setLogs((prev) => {
            const existing = new Set(prev.map((l) => l.id));
            const fresh = data.new_logs.filter((l) => !existing.has(l.id));
            return [...prev.slice(-200), ...fresh];
          });
          setLastLogId(data.latest_id);
        }
      } catch (err) {}
    }, 1500);

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
      await startEsamCrawler();
      setTelemetry((prev) => ({ ...prev, status: 'running' }));
      if (onStatusChange) onStatusChange();
    } catch (e) {
      alert('خطا در شروع خزش ایسام: ' + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  const handleStop = async () => {
    setLoadingAction(true);
    try {
      await stopEsamCrawler();
      setTelemetry((prev) => ({ ...prev, status: 'idle' }));
      if (onStatusChange) onStatusChange();
    } catch (e) {
      alert('خطا در توقف خزش ایسام: ' + e.message);
    } finally {
      setLoadingAction(false);
    }
  };

  const copyLogs = () => {
    const text = logs.map((l) => `[${l.time}] [${l.level}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
  };

  const isRunning = telemetry.status === 'running';

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md shadow-xl mb-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className={`p-2.5 rounded-xl border ${isRunning ? 'bg-orange-500/10 border-orange-500/30 text-orange-400' : 'bg-slate-800/80 border-slate-700 text-slate-400'}`}>
            <Radio className={`w-5 h-5 ${isRunning ? 'animate-pulse text-orange-400' : ''}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">مرکز فرماندهی و مانیتورینگ زنده ایسام (Esam Live Control)</h2>
              <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${isRunning ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 animate-pulse' : 'bg-slate-800 text-slate-400'}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-emerald-400' : 'bg-slate-500'}`}></span>
                {isRunning ? 'خزش ۲۴ ساعته فعال' : 'آماده به کار'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">پایش مستمر مزایدات لحظه‌ای، کالاهای استوک، قطعات کامپیوتر و تغییرات قیمت</p>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-2">
          {isRunning ? (
            <button
              onClick={handleStop}
              disabled={loadingAction}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/20 transition active:scale-95 disabled:opacity-50"
            >
              <Square className="w-4 h-4 fill-current" />
              <span>توقف خزش ایسام</span>
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={loadingAction}
              className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white shadow-lg shadow-orange-600/20 transition active:scale-95 disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>شروع خزش پیوسته ایسام</span>
            </button>
          )}
        </div>
      </div>

      {/* Telemetry Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-4">
        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-400">کالاهای اسکن‌شده</p>
          <p className="text-xl font-extrabold text-white mt-1">
            {Number(telemetry.items_scanned || 0).toLocaleString('fa-IR')}
          </p>
        </div>

        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-400">کالای جدید کشف‌شده</p>
          <p className="text-xl font-extrabold text-emerald-400 mt-1">
            {Number(telemetry.new_items_found || 0).toLocaleString('fa-IR')}
          </p>
        </div>

        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-400">نوسانات قیمتی ثبت‌شده</p>
          <p className="text-xl font-extrabold text-amber-400 mt-1">
            {Number(telemetry.price_changes_detected || 0).toLocaleString('fa-IR')}
          </p>
        </div>

        <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80">
          <p className="text-[11px] font-medium text-slate-400">پیشنهادات جدید مزایده</p>
          <p className="text-xl font-extrabold text-orange-400 mt-1">
            {Number(telemetry.bids_updated || 0).toLocaleString('fa-IR')}
          </p>
        </div>
      </div>

      {/* Live Terminal Console */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden font-mono text-xs shadow-inner">
        <div className="flex items-center justify-between px-3 py-2 bg-slate-900/80 border-b border-slate-800 text-slate-400">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-orange-400" />
            <span className="font-semibold text-slate-300">کنسول لاگ زنده موتور خزش ایسام</span>
            {telemetry.active_category && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-orange-400 border border-slate-700">
                در حال خزش: {telemetry.active_category} (صفحه {telemetry.current_page})
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`p-1 rounded hover:bg-slate-800 transition ${autoScroll ? 'text-orange-400' : 'text-slate-500'}`}
              title="اسکرول خودکار"
            >
              <ArrowDown className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={copyLogs}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="کپی لاگ‌ها"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setLogs([])}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="پاکسازی کنسول"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div
          ref={logContainerRef}
          className="h-44 overflow-y-auto p-3 space-y-1.5 text-right font-vazir text-slate-300 select-text"
          dir="rtl"
        >
          {logs.length === 0 ? (
            <div className="text-slate-500 text-center py-10 font-sans">
              در انتظار شروع خزش و دریافت لاگ‌های زنده ایسام...
            </div>
          ) : (
            logs.map((l) => (
              <div key={l.id} className="flex items-start gap-2 leading-relaxed">
                <span className="text-slate-500 font-mono text-[10px] shrink-0">{l.time}</span>
                <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold shrink-0 ${
                  l.level === 'ERROR' ? 'bg-rose-500/20 text-rose-400' :
                  l.level === 'WARNING' ? 'bg-amber-500/20 text-amber-300' :
                  'bg-sky-500/20 text-sky-400'
                }`}>
                  {l.level}
                </span>
                <span className="text-slate-200 break-words">{l.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
