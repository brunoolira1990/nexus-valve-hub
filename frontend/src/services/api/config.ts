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

/** Extrai mensagem legível de erro da API (DRF). */
export function apiErrorMessage(err: unknown): string {
  const ax = err as AxiosError<{ detail?: string; non_field_errors?: string[]; [k: string]: unknown }>;
  const d = ax.response?.data;
  if (!d) return ax.message || 'Erro de rede';
  if (typeof d === 'string') return d;
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) return d.detail.map(String).join(', ');
  const first = Object.entries(d).find(([, v]) => v != null);
  if (first) {
    const v = first[1];
    if (Array.isArray(v)) return `${first[0]}: ${v.join(', ')}`;
    if (typeof v === 'string') return v;
  }
  return 'Erro ao processar a resposta';
}

export default api;

/** Mantido para compatibilidade; não usar em chamadas reais. */
export const delay = (ms = 300) => new Promise((r) => setTimeout(r, ms));
