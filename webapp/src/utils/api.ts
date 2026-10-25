import { getTelegramInitData } from './telegram';

const getHeaders = (customHeaders: Record<string, string> = {}): Record<string, string> => {
  const initData = getTelegramInitData();
  return {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...(initData ? { 'X-Telegram-Init-Data': initData } : {}),
    ...customHeaders,
  };
};

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const response = await fetch(url, {
    ...options,
    headers: getHeaders((options.headers as Record<string, string>) || {}),
  });

  if (!response.ok) {
    let errorMsg = `Server error (${response.status})`;
    try {
      const data = await response.json();
      if (data && data.detail) {
        errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch (_) {}
    throw new Error(errorMsg);
  }

  return response.json();
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, any>) => {
    let url = endpoint;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          searchParams.append(k, String(v));
        }
      });
      const qs = searchParams.toString();
      if (qs) url += `?${qs}`;
    }
    return apiFetch<T>(url, { method: 'GET' });
  },
  post: <T>(endpoint: string, body?: any) => {
    return apiFetch<T>(endpoint, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  patch: <T>(endpoint: string, body?: any) => {
    return apiFetch<T>(endpoint, {
      method: 'PATCH',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },
  delete: <T>(endpoint: string) => {
    return apiFetch<T>(endpoint, { method: 'DELETE' });
  },
};
