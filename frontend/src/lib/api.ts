import type {
  AIConfig, AutomationCandidate, Explanation, GenerateResult,
  HistoryItem, Lint, Persona, Preset, StreamEvent,
  OptimizeStreamEvent, ReviewReport, ReviewExportFormat, 
} from './types';


function aiHeaders(cfg: AIConfig): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (cfg.provider) h['X-AI-Provider'] = cfg.provider;
  if (cfg.apiKey) h['X-AI-Key'] = cfg.apiKey;
  if (cfg.model) h['X-AI-Model'] = cfg.model;
  if (cfg.baseUrl) h['X-AI-Base-Url'] = cfg.baseUrl;
  h['X-AI-Language'] = currentLocale;
  return h;
}

import type { Locale } from './translations';

let currentLocale: Locale = 'en';
export function setApiLocale(l: Locale) {
  currentLocale = l;
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(message: string, code = 'ERROR', status = 500) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function req<T>(url: string, opts: RequestInit = {}): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(url, opts);
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running on :8000?', 'NETWORK', 0);
  }
  const text = await resp.text();
  const data = text ? JSON.parse(text) : {};
  if (!resp.ok) {
    const detail = (data && (data.detail || data)) as any;
    throw new ApiError(
      detail?.error || detail?.message || `Request failed (${resp.status})`,
      detail?.code || 'ERROR',
      resp.status,
    );
  }
  return data as T;
}

async function streamSSE(url: string, headers: Record<string, string>, bodyObj: unknown, onEvent: (e: StreamEvent) => void): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(url, { method: 'POST', headers, body: JSON.stringify(bodyObj) });
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running on :8000?', 'NETWORK', 0);
  }
  if (!resp.ok || !resp.body) {
    throw new ApiError(`Stream failed (${resp.status})`, 'STREAM', resp.status);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      try {
        onEvent(JSON.parse(payload) as StreamEvent);
      } catch {
        void 0;
      }
    }
  }
}

export const api = {
  health: () => req<{ ok: boolean; version: string }>('/api/health'),
  healthFull: () => req<{ ok: boolean; version: string; checks: Record<string, string> }>('/api/health/full'),
  testLLM: (cfg: AIConfig) =>
    req<{ ok: boolean; reply?: string; error?: string }>('/api/health/llm', {
      method: 'POST',
      headers: aiHeaders(cfg),
      body: JSON.stringify({}),
    }),
  presets: () => req<{ presets: Preset[] }>('/api/presets').then((d) => d.presets),

  lint: (xml: string) =>
    req<Lint>('/api/lint', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ xml }) }),

  generate: (description: string, cfg: AIConfig) =>
    req<GenerateResult>('/api/generate', { method: 'POST', headers: aiHeaders(cfg), body: JSON.stringify({ description }) }),

  fix: (xml: string, issues: unknown[], cfg: AIConfig) =>
    req<{ xml: string; lint: Lint }>('/api/fix', { method: 'POST', headers: aiHeaders(cfg), body: JSON.stringify({ xml, issues }) }),

  explain: (xml: string, persona: Persona, cfg: AIConfig) =>
    req<Explanation>('/api/explain', { method: 'POST', headers: aiHeaders(cfg), body: JSON.stringify({ xml, persona }) }),

  automate: (xml: string, cfg: AIConfig) =>
    req<{ candidates: AutomationCandidate[] }>('/api/automate', { method: 'POST', headers: aiHeaders(cfg), body: JSON.stringify({ xml }) }).then((d) => d.candidates),
  
  review: (xml: string, cfg: AIConfig) =>
    req<ReviewReport>('/api/review', { method: 'POST', headers: aiHeaders(cfg), body: JSON.stringify({ xml }) }),
  
  optimizeStream: (xml: string, cfg: AIConfig, onEvent: (e:
    OptimizeStreamEvent) => void) =>
    streamSSE('/api/optimize/stream', aiHeaders(cfg), { xml }, onEvent as (e: unknown) => void),

  
  enhance: (description: string, cfg: AIConfig) =>
    req<{ enhanced: string }>('/api/enhance', { method: 'POST', headers: aiHeaders(cfg), body: JSON.stringify({ description }) }).then((d) => d.enhanced),



  exportPowerAutomate: async (xml: string): Promise<{ blob: Blob; filename: string }> => {
    let resp: Response;
    try {
      resp = await fetch('/api/export/power-automate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ xml }),
      });
    } catch {
      throw new ApiError('Cannot reach the server. Is the backend running on :8000?', 'NETWORK', 0);
    }
    if (!resp.ok) {
      let msg = `Export failed (${resp.status})`;
      try {
        const data = await resp.json();
        msg = (data?.detail?.error || data?.error || msg) as string;
      } catch {
        void 0;
      }
      throw new ApiError(msg, 'EXPORT', resp.status);
    }
    const disposition = resp.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : 'power-automate-package.zip';
    const blob = await resp.blob();
    return { blob, filename };
  },
    exportReview: async (report: ReviewReport, format: ReviewExportFormat, processName?: string): Promise<{ blob: Blob; filename: string }> => {
    let resp: Response;
    try {
      resp = await fetch('/api/review/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report, format, processName }),
      });
    } catch {
      throw new ApiError('Cannot reach the server. Is the backend running on :8000?', 'NETWORK', 0);
    }
    if (!resp.ok) {
      let msg = `Export failed (${resp.status})`;
      try {
        const data = await resp.json();
        msg = (data?.detail?.error || data?.error || msg) as string;
      } catch { /* ignore */ }
      throw new ApiError(msg, 'EXPORT', resp.status);
    }
    const disposition = resp.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `process_review.${format}`;
    const blob = await resp.blob();
    return { blob, filename };
  },
  history: () => req<{ history: HistoryItem[] }>('/api/history').then((d) => d.history),
  suggest: (query: string) =>
    req<{ suggestions: HistoryItem[] }>('/api/history/suggest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }) }).then((d) => d.suggestions),
  deleteHistory: (id: number) => req(`/api/history/${id}`, { method: 'DELETE' }),
  pinHistory: (id: number) => req(`/api/history/${id}/pin`, { method: 'POST' }),
  clearHistory: () => req('/api/history', { method: 'DELETE' }),

  generateStream: (description: string, cfg: AIConfig, onEvent: (e: StreamEvent) => void) =>
    streamSSE('/api/generate/stream', aiHeaders(cfg), { description }, onEvent),

  editStream: (xml: string, instruction: string, cfg: AIConfig, onEvent: (e: StreamEvent) => void) =>
    streamSSE('/api/edit/stream', aiHeaders(cfg), { xml, instruction }, onEvent),
};


