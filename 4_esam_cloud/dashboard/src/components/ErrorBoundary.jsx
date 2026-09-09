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
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 rounded-2xl bg-rose-950/30 border border-rose-500/40 text-center my-8">
          <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-white mb-2">خطا در بارگذاری کامپوننت</h3>
          <p className="text-xs text-rose-300 font-mono mb-4">{this.state.error?.message || 'خطای ناشناخته رخ داد.'}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-xl bg-rose-600 text-white text-xs font-bold hover:bg-rose-500 transition inline-flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            <span>بارگذاری مجدد صفحه</span>
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
