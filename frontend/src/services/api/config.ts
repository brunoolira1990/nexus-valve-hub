import axios, { type AxiosError } from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL?.trim() || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

type ApiErrorMessageOptions = {
  fallback?: string;
  preferGeneric?: boolean;
};

function statusMessage(status?: number): string | null {
  if (status === 401) return 'Sua sessao expirou. Faça login novamente.';
  if (status === 403) return 'Você não tem permissão para acessar este recurso.';
  if (status === 404) return 'Recurso não encontrado.';
  if (status && status >= 500) return 'Erro interno do servidor. Tente novamente em instantes.';
  return null;
}

/** Extrai mensagem legível de erro da API (DRF). */
export function apiErrorMessage(err: unknown, options: ApiErrorMessageOptions = {}): string {
  const { fallback = 'Não foi possível concluir a operação.', preferGeneric = false } = options;
  const ax = err as AxiosError<{ detail?: string; non_field_errors?: string[]; [k: string]: unknown }>;
  const d = ax.response?.data;
  const status = ax.response?.status;

  const sanitize = (message: string, fallback: string) => {
    if (!message) return fallback;
    const normalized = String(message).replace(/\s+/g, ' ').trim();
    const withoutTags = normalized.replace(/<[^>]*>/g, '').trim();
    const value = withoutTags || fallback;
    return value.length > 180 ? `${value.slice(0, 177)}...` : value;
  };

  const hasHtmlPayload =
    typeof d === 'string' && /<\/?(html|head|body|div|pre|script|style)[\s>]/i.test(d);

  const knownStatusMessage = statusMessage(status);
  if (knownStatusMessage) {
    return knownStatusMessage;
  }
  if (preferGeneric) {
    return fallback;
  }

  if (!d) {
    return sanitize(ax.message || '', fallback || 'Erro de conexão com o servidor.');
  }
  if (typeof d === 'string') {
    if (hasHtmlPayload) return fallback;
    return sanitize(d, fallback);
  }
  if (typeof d.code === 'string' && d.code === 'token_not_valid') {
    return 'Sua sessao expirou. Faça login novamente.';
  }
  if (typeof d.detail === 'string') return sanitize(d.detail, fallback);
  if (Array.isArray(d.detail)) return sanitize(d.detail.map(String).join(', '), fallback);
  const first = Object.entries(d).find(([, v]) => v != null);
  if (first) {
    const v = first[1];
    if (Array.isArray(v)) return sanitize(`${first[0]}: ${v.join(', ')}`, fallback);
    if (typeof v === 'string') return sanitize(v, fallback);
  }
  return fallback;
}

export default api;

/** Mantido para compatibilidade; não usar em chamadas reais. */
export const delay = (ms = 300) => new Promise((r) => setTimeout(r, ms));
