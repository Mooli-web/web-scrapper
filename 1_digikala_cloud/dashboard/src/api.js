// API Client with Token Auth, Clean Param Sanitization, and Real Diagnostic Helpers

const API_BASE = '/api';

export const getAuthToken = () => localStorage.getItem('auth_token');

export const setAuthToken = (token) => {
  if (token) localStorage.setItem('auth_token', token);
  else localStorage.removeItem('auth_token');
};

export const logout = () => {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
  window.location.reload();
};

const sanitizeParams = (params = {}) => {
  const clean = {};
  for (const [key, value] of Object.entries(params)) {
    if (
      value !== undefined &&
      value !== null &&
      value !== '' &&
      value !== 'undefined' &&
      value !== 'null'
    ) {
      clean[key] = value;
    }
  }
  return clean;
};

const authFetch = async (url, options = {}) => {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401 && token) {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
  }
  return res;
};

export const login = async (username, password) => {
  const res = await fetch(`${API_BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'نام کاربری یا رمز عبور اشتباه است');
  }
  const data = await res.json();
  setAuthToken(data.access_token);
  localStorage.setItem('auth_user', JSON.stringify(data.user));
  return data;
};

export const checkAuthStatus = async () => {
  try {
    const res = await authFetch(`${API_BASE}/auth/me`);
    if (res.ok) return await res.json();
    return null;
  } catch {
    return null;
  }
};

export const formatToman = (amount) => {
  if (!amount || isNaN(amount) || amount === 0) return '۰ تومان';
  return Math.round(Number(amount)).toLocaleString('fa-IR') + ' تومان';
};

export const formatPercent = (val) => {
  if (!val || isNaN(val) || val === 0) return '۰٪';
  return (Math.round(Number(val) * 10) / 10).toLocaleString('fa-IR') + '٪';
};

export const formatPersianDate = (dateStr) => {
  if (!dateStr) return '-';
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat('fa-IR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(d);
  } catch {
    return dateStr;
  }
};

export const fetchOverview = async () => {
  try {
    const res = await authFetch(`${API_BASE}/overview`);
    if (!res.ok) throw new Error('Overview fetch failed');
    return await res.json();
  } catch {
    return {
      total_products: 0,
      total_categories: 17,
      active_discounts: 0,
      in_stock_count: 0,
      out_of_stock_count: 0,
      avg_discount_percent: 0.0,
      fake_discounts_count: 0,
      genuine_discounts_count: 0,
      active_seller_wars: 0,
      events_24h: 0,
      high_severity_24h: 0,
      db_usage_percent: 0.0,
      db_size_mb: 0.0,
      database_health: { connected: false, status: 'disconnected', latency_ms: 0 },
      crawler_telemetry: { status: 'idle', products_scanned: 0, new_products_found: 0, price_changes_detected: 0 },
      divar_telemetry: { status: 'idle', products_scanned: 0, new_products_found: 0, price_changes_detected: 0 },
      recent_deals: []
    };
  }
};

export const fetchCategories = async () => {
  try {
    const res = await authFetch(`${API_BASE}/categories`);
    if (!res.ok) throw new Error('Categories fetch failed');
    return await res.json();
  } catch {
    return [];
  }
};

export const fetchProducts = async (params = {}) => {
  try {
    const clean = sanitizeParams(params);
    const q = new URLSearchParams(clean).toString();
    const res = await authFetch(`${API_BASE}/products${q ? `?${q}` : ''}`);
    if (!res.ok) throw new Error('Products fetch failed');
    return await res.json();
  } catch {
    return { items: [], total: 0, page: 1, page_size: 20, total_pages: 1 };
  }
};

export const fetchProductDetail = async (id) => {
  try {
    const res = await authFetch(`${API_BASE}/products/${id}`);
    if (!res.ok) throw new Error('Product not found');
    return await res.json();
  } catch {
    return null;
  }
};

export const fetchFakeDiscounts = async (params = {}) => {
  try {
    const clean = sanitizeParams(params);
    const q = new URLSearchParams(clean).toString();
    const res = await authFetch(`${API_BASE}/fake-discounts${q ? `?${q}` : ''}`);
    if (!res.ok) throw new Error('Fake discounts fetch failed');
    return await res.json();
  } catch {
    return { items: [], total: 0, page: 1, page_size: 20, stats: {} };
  }
};

export const fetchSellerWars = async (params = {}) => {
  try {
    const clean = sanitizeParams(params);
    const q = new URLSearchParams(clean).toString();
    const res = await authFetch(`${API_BASE}/seller-war/battles${q ? `?${q}` : ''}`);
    if (!res.ok) throw new Error('Seller war fetch failed');
    return await res.json();
  } catch {
    return { battles: [], top_sellers: [], total_battles: 0 };
  }
};

export const fetchEvents = async (params = {}) => {
  try {
    const clean = sanitizeParams(params);
    const q = new URLSearchParams(clean).toString();
    const res = await authFetch(`${API_BASE}/events${q ? `?${q}` : ''}`);
    if (!res.ok) throw new Error('Events fetch failed');
    return await res.json();
  } catch {
    return [];
  }
};

export const fetchStatus = async () => {
  try {
    const res = await fetch(`${API_BASE}/status`);
    if (!res.ok) throw new Error('Status failed');
    return await res.json();
  } catch {
    return {
      status: 'disconnected',
      database: { connected: false, status: 'disconnected', latency_ms: 0 },
      crawler_telemetry: { status: 'idle' },
      divar_telemetry: { status: 'idle' }
    };
  }
};

export const fetchDbSize = async () => {
  try {
    const res = await authFetch(`${API_BASE}/db-size`);
    if (!res.ok) throw new Error('DB size failed');
    return await res.json();
  } catch {
    return { tables: [], total_rows: 0, estimated_storage_mb: 0.0, estimated_storage_gb: 0.0, quota_max_gb: 5.0, usage_percent: 0.0, status: 'healthy' };
  }
};

export const testDbConnection = async () => {
  const res = await fetch(`${API_BASE}/database/test-connection`);
  return await res.json();
};

export const testDigikalaConnection = async () => {
  const res = await fetch(`${API_BASE}/digikala/test-connection`);
  return await res.json();
};

export const testDivarConnection = async () => {
  const res = await fetch(`${API_BASE}/divar/test-connection`);
  return await res.json();
};

export const startContinuousCrawler = async () => {
  const res = await authFetch(`${API_BASE}/crawler/start`, { method: 'POST' });
  return await res.json();
};

export const stopContinuousCrawler = async () => {
  const res = await authFetch(`${API_BASE}/crawler/stop`, { method: 'POST' });
  return await res.json();
};

export const startDivarCrawler = async () => {
  const res = await authFetch(`${API_BASE}/divar/start`, { method: 'POST' });
  return await res.json();
};

export const stopDivarCrawler = async () => {
  const res = await authFetch(`${API_BASE}/divar/stop`, { method: 'POST' });
  return await res.json();
};

export const wipeDatabase = async () => {
  const res = await authFetch(`${API_BASE}/wipe-database`, { method: 'POST' });
  if (!res.ok) throw new Error('خطا در پاکسازی دیتابیس');
  return await res.json();
};
