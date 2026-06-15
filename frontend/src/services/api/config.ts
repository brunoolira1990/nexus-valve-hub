import axios, { type AxiosError } from 'axios';
import { extrairErrosXsd, formatNfeErrosLista } from '@/lib/nfeXsdErros';
import { clearDashboardPermissoesCache } from './dashboardPermissoesCache';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL?.trim() || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
});

export const SESSION_EXPIRED_MESSAGE =
  'Sessão expirada ou acesso não autorizado. Entre novamente para continuar.';

let handling401Redirect = false;

export function getApiErrorStatus(err: unknown): number | undefined {
  return (err as AxiosError)?.response?.status;
}

export function isApiUnauthorized(err: unknown): boolean {
  return getApiErrorStatus(err) === 401;
}

export function isApiForbidden(err: unknown): boolean {
  return getApiErrorStatus(err) === 403;
}

export function clearAuthSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  clearDashboardPermissoesCache();
}

function maybeRedirectToLogin() {
  if (handling401Redirect) return;
  if (typeof window === 'undefined') return;
  if (window.location.pathname.startsWith('/login')) return;
  handling401Redirect = true;
  window.location.assign('/login');
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (isApiUnauthorized(error)) {
      clearAuthSession();
      maybeRedirectToLogin();
    }
    return Promise.reject(error);
  },
);

type ApiErrorMessageOptions = {
  fallback?: string;
  preferGeneric?: boolean;
};

/** Respostas 403 do DRF (permissões Django). Usado também em `formatApiErrors` (Qualidade). */
export const PERMISSION_DENIED_MESSAGE = 'Você não tem permissão para executar esta ação.';

function statusMessage(status?: number): string | null {
  if (status === 401) return SESSION_EXPIRED_MESSAGE;
  if (status === 403) return PERMISSION_DENIED_MESSAGE;
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
    return SESSION_EXPIRED_MESSAGE;
  }
  if (typeof d.mensagem === 'string') return sanitize(d.mensagem, fallback);
  if (d && typeof d === 'object') {
    const errosXsd = formatNfeErrosLista(extrairErrosXsd(d as Record<string, unknown>));
    if (errosXsd) return sanitize(errosXsd, fallback);
  }
  if (Array.isArray(d.erros) && d.erros.length) {
    const formatted = formatNfeErrosLista(d.erros);
    if (formatted) return sanitize(formatted, fallback);
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

/** Mensagem para alert/toast sem vazar HTML de páginas de erro do Django. */
export function alertMessageFromApiError(err: unknown): string {
  const ax = err as AxiosError<Record<string, unknown> | string>;
  const status = ax.response?.status;
  const d = ax.response?.data;

  if (status != null && status >= 500) {
    return 'Erro interno ao salvar o pedido de compra. Verifique os dados e tente novamente.';
  }

  if (typeof d === 'string') {
    const s = d.trim();
    const sl = s.toLowerCase();
    if (sl.startsWith('<!doctype') || sl.startsWith('<html')) {
      return 'Não foi possível salvar o pedido de compra. Verifique os dados e tente novamente.';
    }
    return sanitizeForUser(s, 'Não foi possível salvar o pedido de compra. Verifique os dados e tente novamente.');
  }

  if (d && typeof d === 'object' && !Array.isArray(d)) {
    const detail = d.detail;
    if (typeof detail === 'string') return sanitizeForUser(detail, 'Não foi possível salvar o pedido de compra.');
    if (Array.isArray(detail)) return detail.map(String).join('\n');

    const lines: string[] = [];
    for (const [k, v] of Object.entries(d)) {
      if (k === 'detail') continue;
      if (Array.isArray(v)) lines.push(...v.map((x) => `${k}: ${String(x)}`));
      else if (typeof v === 'string') lines.push(`${k}: ${v}`);
    }
    if (lines.length) return lines.join('\n');
  }

  return 'Não foi possível salvar o pedido de compra. Verifique os dados e tente novamente.';
}

function sanitizeForUser(message: string, fallback: string): string {
  if (!message) return fallback;
  const normalized = String(message).replace(/\s+/g, ' ').trim();
  const withoutTags = normalized.replace(/<[^>]*>/g, '').trim();
  const value = withoutTags || fallback;
  return value.length > 220 ? `${value.slice(0, 217)}...` : value;
}

/** Mantido para compatibilidade; não usar em chamadas reais. */
export const delay = (ms = 300) => new Promise((r) => setTimeout(r, ms));
