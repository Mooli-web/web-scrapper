import React, { useState, useEffect } from 'react';
import { Smartphone, CheckCircle2, AlertCircle, X, RefreshCw } from 'lucide-react';
import { testDivarConnection } from '../api';

export default function DivarTestModal({ isOpen, onClose }) {
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  const runTest = async () => {
    setTesting(true);
    try {
      const data = await testDivarConnection();
      setTestResult(data);
    } catch (err) {
      setTestResult({
        reachable: false,
        status: 'error',
        latency_ms: 0,
        error: String(err)
      });
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => {
    if (isOpen) runTest();
  }, [isOpen]);

  if (!isOpen) return null;

  const isReachable = Boolean(testResult?.reachable);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="glass-card bg-slate-900 border border-slate-700 rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-5 text-right relative">
        <button
          onClick={onClose}
          className="absolute left-4 top-4 text-slate-400 hover:text-white p-1 rounded-lg bg-slate-800 cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className={`w-11 h-11 rounded-2xl flex items-center justify-center border shadow-lg ${
            isReachable
              ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
              : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
          }`}>
            <Smartphone className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-black text-white">تست زنده دسترسی به API دیوار (Divar)</h3>
            <p className="text-xs text-slate-400">سنجش دسترسی کانتینر Render به سرورهای api.divar.ir</p>
          </div>
        </div>

        {/* Diagnostics Output */}
        {testing ? (
          <div className="py-12 text-center space-y-2">
            <RefreshCw className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
            <p className="text-xs text-slate-300 font-semibold">در حال ارسال پروب آزمایشی به دیوار...</p>
          </div>
        ) : testResult ? (
          <div className="space-y-3">
            <div className={`p-4 rounded-2xl border flex items-start gap-3 ${
              isReachable
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
            }`}>
              {isReachable ? (
                <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              )}
              <div className="text-xs space-y-1">
                <strong className="block font-bold">
                  {isReachable ? 'ارتباط مستقیم با API دیوار برقرار است' : 'عدم دسترسی به سرورهای دیوار (Timeout یا فیلتر)'}
                </strong>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {isReachable
                    ? `پاسخ با کد وضعیت ${testResult.status_code} و دریافت ${testResult.items_found} آگهی دیجیتال تستی.`
                    : testResult.error || testResult.hint}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">تاخیر پاسخ API دیوار:</span>
                <span className="font-mono font-bold text-emerald-400 text-sm">
                  {testResult.latency_ms} ms
                </span>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">کد وضعیت HTTP:</span>
                <span className="font-mono font-bold text-white text-xs">
                  {testResult.status_code || testResult.status}
                </span>
              </div>
            </div>
          </div>
        ) : null}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800">
          <button
            onClick={runTest}
            disabled={testing}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${testing ? 'animate-spin' : ''}`} />
            <span>تست مجدد</span>
          </button>

          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
          >
            بستن
          </button>
        </div>
      </div>
    </div>
  );
}
