import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('React Dashboard Error Caught:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6 text-right" dir="rtl">
          <div className="glass-card bg-slate-900/90 border border-slate-700 rounded-3xl p-8 max-w-lg w-full shadow-2xl space-y-4 text-center">
            <div className="w-14 h-14 rounded-2xl bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-7 h-7" />
            </div>
            <h2 className="text-lg font-black text-white">خطا در بارگذاری رابط کاربری</h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              با فشردن دکمه زیر صفحه را تازه‌سازی کنید.
            </p>
            {this.state.error && (
              <pre className="p-3 rounded-xl bg-slate-950 text-[10px] text-rose-400 font-mono text-left overflow-x-auto" dir="ltr">
                {String(this.state.error)}
              </pre>
            )}
            <button
              onClick={this.handleReload}
              className="px-6 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center justify-center gap-2 mx-auto transition cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              <span>بارگذاری مجدد داشبورد</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
