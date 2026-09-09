const BASE_URL = '/api';

function getAuthHeaders() {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
}

export async function fetchOverviewStats() {
  const res = await fetch(`${BASE_URL}/esam/overview`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در دریافت آمار کلی ایسام');
  return res.json();
}

export async function fetchEsamItems({ search, category, condition, auction_only, sort_by, sort_order, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (category && category !== 'all') params.append('category', category);
  if (condition && condition !== 'all') params.append('condition', condition);
  if (auction_only) params.append('auction_only', 'true');
  if (sort_by) params.append('sort_by', sort_by);
  if (sort_order) params.append('sort_order', sort_order);
  params.append('limit', limit);
  params.append('offset', offset);

  const res = await fetch(`${BASE_URL}/esam/items?${params.toString()}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در دریافت لیست کالاهای ایسام');
  return res.json();
}

export async function fetchActiveAuctions({ limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit, offset });
  const res = await fetch(`${BASE_URL}/esam/auctions?${params.toString()}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در دریافت لیست مزایدات فعال');
  return res.json();
}

export async function fetchEsamEvents({ event_type, severity, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (event_type && event_type !== 'all') params.append('event_type', event_type);
  if (severity && severity !== 'all') params.append('severity', severity);
  params.append('limit', limit);
  params.append('offset', offset);

  const res = await fetch(`${BASE_URL}/esam/events?${params.toString()}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در دریافت رویدادهای قیمتی ایسام');
  return res.json();
}

export async function fetchEsamCategories() {
  const res = await fetch(`${BASE_URL}/esam/categories`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در دریافت دسته‌بندی‌های ایسام');
  return res.json();
}

export async function startEsamCrawler() {
  const res = await fetch(`${BASE_URL}/crawler/start`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('خطا در شروع خزش ایسام');
  return res.json();
}

export async function stopEsamCrawler() {
  const res = await fetch(`${BASE_URL}/crawler/stop`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('خطا در توقف خزش ایسام');
  return res.json();
}

export async function fetchCrawlerLogsStream(afterId = 0) {
  const res = await fetch(`${BASE_URL}/crawler/logs-stream?after_id=${afterId}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در دریافت جریان لاگ');
  return res.json();
}

export async function testDbConnection() {
  const res = await fetch(`${BASE_URL}/database/test-connection`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در اتصال به پایگاه داده');
  return res.json();
}

export async function testEsamProbe(slug = 'search/laptop?cc=40100', page = 1) {
  const params = new URLSearchParams({ slug, page });
  const res = await fetch(`${BASE_URL}/esam/test-probe?${params.toString()}`, { headers: getAuthHeaders() });
  if (!res.ok) throw new Error('خطا در تست اسکرپر ایسام');
  return res.json();
}

export async function triggerCrawlerBatch(category_key = 'laptop', page = 1) {
  const params = new URLSearchParams({ category_key, page });
  const res = await fetch(`${BASE_URL}/crawler/trigger-batch?${params.toString()}`, {
    method: 'POST',
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error('خطا در اجرای دستی اسکرپ');
  return res.json();
}
