import api from './config';
import type { Empresa } from '@/types';

const path = 'empresas/';

function stripReadOnly(e: Partial<Empresa>): Record<string, unknown> {
  const x: Record<string, unknown> = { ...e };
  delete x.id;
  delete x.certificado_arquivo;
  delete x.logotipo;
  delete x.criado_em;
  delete x.atualizado_em;
  if (!x.senha_certificado) delete x.senha_certificado;
  return x;
}

function buildFormData(data: Partial<Empresa>, files?: { cert?: File | null; logo?: File | null }) {
  const body = stripReadOnly(data);
  const fd = new FormData();
  Object.entries(body).forEach(([k, v]) => {
    if (v === null || v === undefined) return;
    fd.append(k, String(v));
  });
  if (files?.cert) fd.append('certificado_arquivo', files.cert);
  if (files?.logo) fd.append('logotipo', files.logo);
  return fd;
}

export const empresasService = {
  getAll: async () => (await api.get<Empresa[]>(path)).data,
  getById: async (id: number) => (await api.get<Empresa>(`${path}${id}/`)).data,
  create: async (data: Omit<Empresa, 'id'>, files?: { cert?: File | null; logo?: File | null }) => {
    const fd = buildFormData(data, files);
    const { data: created } = await api.post<Empresa>(path, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return created;
  },
  update: async (
    id: number,
    data: Partial<Empresa>,
    files?: { cert?: File | null; logo?: File | null },
  ) => {
    const fd = buildFormData(data, files);
    const { data: updated } = await api.patch<Empresa>(`${path}${id}/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return updated;
  },
  delete: async (id: number) => {
    await api.delete(`${path}${id}/`);
  },
};
