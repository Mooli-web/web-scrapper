import React, { useState } from 'react';
import { Lock, User, Key, ShieldCheck, AlertCircle, ArrowLeft } from 'lucide-react';
import { login } from '../api';

export default function LoginModal({ onLoginSuccess }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await login(username, password);
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'نام کاربری یا رمز عبور اشتباه است');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-xl flex items-center justify-center p-4">
      <div className="glass-card bg-slate-900/90 border border-slate-700/80 rounded-3xl p-8 max-w-md w-full shadow-2xl space-y-6 text-right">
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-rose-600 to-rose-400 flex items-center justify-center mx-auto shadow-lg text-white">
            <Lock className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-black text-white">ورود به سامانه هوش بازار</h2>
          <p className="text-xs text-slate-400">
            برای دسترسی به داشبورد و کنترل پنل خزش، مشخصات را وارد کنید.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-2xl bg-rose-500/15 border border-rose-500/30 flex items-center gap-2 text-rose-400 text-xs font-semibold">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 block">نام کاربری</label>
            <div className="relative">
              <User className="w-4 h-4 absolute right-3.5 top-3 text-slate-400" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="w-full bg-slate-950/80 border border-slate-700 rounded-xl pr-10 pl-4 py-2.5 text-xs text-white focus:outline-none focus:border-rose-500 transition"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 block">رمز عبور</label>
            <div className="relative">
              <Key className="w-4 h-4 absolute right-3.5 top-3 text-slate-400" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950/80 border border-slate-700 rounded-xl pr-10 pl-4 py-2.5 text-xs text-white focus:outline-none focus:border-rose-500 transition"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg transition cursor-pointer disabled:opacity-50"
          >
            <span>{loading ? 'در حال بررسی...' : 'ورود امن به داشبورد'}</span>
            <ArrowLeft className="w-4 h-4" />
          </button>
        </form>

        <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <span className="text-slate-300 font-semibold block">پیش‌فرض:</span>
            <span>کاربر: <code className="text-rose-400">admin</code> | رمز: <code className="text-rose-400">admin123</code></span>
          </div>
        </div>
      </div>
    </div>
  );
}
