// 运行时可通过 VITE_API_BASE 覆盖；部署到静态 Pages 时需设为后端绝对路径。
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '/api';

function getToken(): string | null {
  return localStorage.getItem('token');
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(options.headers as Record<string, string> || {}),
  };

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(body.detail || `请求失败 (${resp.status})`);
  }

  return resp.json();
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request<{ access_token: string; username: string; is_admin: boolean }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  register: (username: string, password: string) =>
    request<{ access_token: string; username: string; is_admin: boolean }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => request<{ id: number; username: string; is_admin: boolean }>('/auth/me'),

  // Game Sessions
  createSession: (data: { title: string; scenario: string; character_name: string; character_class: string }) =>
    request<any>('/game/sessions', { method: 'POST', body: JSON.stringify(data) }),

  listSessions: () => request<{ sessions: any[] }>('/game/sessions'),

  getSession: (id: string) => request<{ messages: any[]; state: any }>(`/game/sessions/${id}`),

  deleteSession: (id: string) => request<any>(`/game/sessions/${id}`, { method: 'DELETE' }),

  renameSession: (id: string, title: string) =>
    request<any>(`/game/sessions/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),

  exportSession: async (id: string) => {
    const resp = await fetch(`${API_BASE}/game/sessions/${id}/export`, {
      headers: authHeaders(),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(body.detail || '导出失败');
    }
    const text = await resp.text();
    const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const disposition = resp.headers.get('Content-Disposition') || '';
    const filenameMatch = disposition.match(/filename\*?=(?:UTF-8'')?(.+)/i);
    a.download = filenameMatch ? decodeURIComponent(filenameMatch[1]) : '冒险日志.md';
    a.href = url;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Game Action (SSE) with abort + automatic reconnect on transient connection failures
  // before any data was received. Once tokens start arriving, errors propagate to the caller.
  submitAction: async function* (
    sessionId: string,
    content: string,
    opts: { signal?: AbortSignal; maxRetries?: number; onRetry?: (attempt: number, err: unknown) => void } = {},
  ) {
    const { signal, maxRetries = 2, onRetry } = opts;
    let attempt = 0;
    let receivedAny = false;

    while (true) {
      let resp: Response;
      try {
        resp = await fetch(`${API_BASE}/game/sessions/${sessionId}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ content }),
          signal,
        });
      } catch (err: any) {
        if (err?.name === 'AbortError') return;
        if (!receivedAny && attempt < maxRetries) {
          attempt += 1;
          onRetry?.(attempt, err);
          await new Promise((r) => setTimeout(r, 400 * Math.pow(2, attempt - 1)));
          continue;
        }
        throw err;
      }

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(body.detail || '请求失败');
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                receivedAny = true;
                yield data;
              } catch {}
            }
          }
        }
        return;
      } catch (err: any) {
        try { reader.cancel(); } catch {}
        if (err?.name === 'AbortError') return;
        // Mid-stream failure — do NOT silently retry (action might already be persisted server-side).
        throw err;
      }
    }
  },

  // Admin
  getAdminStats: () => request<any>('/admin/stats'),
  getAdminHealth: () => request<any>('/admin/health'),
  getLlmTrend: (hours = 24) => request<any>(`/admin/llm-trend?hours=${hours}`),
  exportLlmUsage: async (days: number, fmt: 'csv' | 'json') => {
    const resp = await fetch(`${API_BASE}/admin/llm-export?days=${days}&fmt=${fmt}`, {
      headers: authHeaders(),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(body.detail || '导出失败');
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const disposition = resp.headers.get('Content-Disposition') || '';
    const m = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    a.download = m ? decodeURIComponent(m[1]) : `llm-usage.${fmt}`;
    a.href = url;
    a.click();
    URL.revokeObjectURL(url);
  },
  getAdminLogs: (params: { page?: number; page_size?: number; action?: string; username?: string }) => {
    const qs = new URLSearchParams();
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    if (params.action) qs.set('action', params.action);
    if (params.username) qs.set('username', params.username);
    return request<any>(`/admin/logs?${qs}`);
  },
  getAdminUsers: (params: { page?: number }) => {
    const qs = new URLSearchParams();
    if (params.page) qs.set('page', String(params.page));
    return request<any>(`/admin/users?${qs}`);
  },

  // World Book
  getWorldEntries: (params: { scenario?: string; layer?: string; page?: number }) => {
    const qs = new URLSearchParams();
    if (params.scenario) qs.set('scenario', params.scenario);
    if (params.layer) qs.set('layer', params.layer);
    if (params.page) qs.set('page', String(params.page));
    return request<any>(`/admin/world-entries?${qs}`);
  },
  createWorldEntry: (data: any) =>
    request<any>('/admin/world-entries', { method: 'POST', body: JSON.stringify(data) }),
  updateWorldEntry: (id: number, data: any) =>
    request<any>(`/admin/world-entries/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteWorldEntry: (id: number) =>
    request<any>(`/admin/world-entries/${id}`, { method: 'DELETE' }),
  reembedWorldEntries: () =>
    request<{ processed: number; success: number; skipped: number }>(
      '/admin/world-entries/reembed',
      { method: 'POST' },
    ),

  // Prompt Templates
  getPromptTemplates: () => request<any>('/admin/prompt-templates'),
  updatePromptTemplate: (id: number, data: any) =>
    request<any>(`/admin/prompt-templates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Game Events (事件池)
  getGameEvents: (params: { category?: string; scenario?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.category) qs.set('category', params.category);
    if (params.scenario) qs.set('scenario', params.scenario);
    const suffix = qs.toString() ? `?${qs}` : '';
    return request<{ events: any[] }>(`/admin/game-events${suffix}`);
  },
  createGameEvent: (data: any) =>
    request<any>('/admin/game-events', { method: 'POST', body: JSON.stringify(data) }),
  updateGameEvent: (id: number, data: any) =>
    request<any>(`/admin/game-events/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteGameEvent: (id: number) =>
    request<any>(`/admin/game-events/${id}`, { method: 'DELETE' }),

  // Settings
  getApiKeys: () => request<{ keys: any[] }>('/settings/apikeys'),
  updateApiKey: (data: { provider: string; api_key: string; base_url: string; model: string }) =>
    request<any>('/settings/apikeys', { method: 'PUT', body: JSON.stringify(data) }),
  deleteApiKey: (provider: string) =>
    request<any>(`/settings/apikeys/${provider}`, { method: 'DELETE' }),

  // Custom Stories (自编故事)
  importStory: (data: { title: string; content: string }) =>
    request<any>('/stories', { method: 'POST', body: JSON.stringify(data) }),
  listStories: () => request<{ stories: any[] }>('/stories'),
  getStory: (id: number) => request<any>(`/stories/${id}`),
  deleteStory: (id: number) => request<any>(`/stories/${id}`, { method: 'DELETE' }),
};
