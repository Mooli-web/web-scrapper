const API_BASE = '/api';

export const getAuthToken = () => localStorage.getItem('divar_auth_token');

export const setAuthToken = (token) => {
  if (token) localStorage.setItem('divar_auth_token', token);
  else localStorage.removeItem('divar_auth_token');
};

export const logout = () => {
  localStorage.removeItem('divar_auth_token');
  localStorage.removeItem('divar_auth_user');
  window.location.reload();
};

const sanitizeParams = (params = {}) => {
  const clean = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '' && value !== 'undefined' && value !== 'null') {
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
    localStorage.removeItem('divar_auth_token');
    localStorage.removeItem('divar_auth_user');
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
  localStorage.setItem('divar_auth_user', JSON.stringify(data.user));
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
    if (!res.ok) throw new Error('Overview failed');
    return await res.json();
  } catch {
    return {
      total_posts: 0,
      like_new_count: 0,
      brand_new_count: 0,
      avg_price: 0,
      events_24h: 0,
      database_health: { connected: false, status: 'disconnected', latency_ms: 0 },
      crawler_telemetry: { status: 'idle', posts_scanned: 0, new_posts_found: 0 },
      recent_ads: []
    };
  }
};

export const fetchCategories = async () => {
  try {
    const res = await authFetch(`${API_BASE}/categories`);
    return await res.json();
  } catch {
    return [];
  }
};

export const fetchPosts = async (params = {}) => {
  try {
    const clean = sanitizeParams(params);
    const q = new URLSearchParams(clean).toString();
    const res = await authFetch(`${API_BASE}/posts${q ? `?${q}` : ''}`);
    if (!res.ok) throw new Error('Posts fetch failed');
    return await res.json();
  } catch {
    return { items: [], total: 0, page: 1, page_size: 20, total_pages: 1 };
  }
};

export const testDbConnection = async () => {
  const res = await fetch(`${API_BASE}/database/test-connection`);
  return await res.json();
};

export const testDivarConnection = async () => {
  const res = await fetch(`${API_BASE}/divar/test-connection`);
  return await res.json();
};

export const startCrawler = async () => {
  const res = await authFetch(`${API_BASE}/crawler/start`, { method: 'POST' });
  return await res.json();
};

export const stopCrawler = async () => {
  const res = await authFetch(`${API_BASE}/crawler/stop`, { method: 'POST' });
  return await res.json();
};

export const wipeDatabase = async () => {
  const res = await authFetch(`${API_BASE}/wipe-database`, { method: 'POST' });
  return await res.json();
};
