import { AxiosError } from 'axios';
import api, { apiErrorMessage } from './config';
import type { CertificadoQualidade, CorridaDisponivelCertificadoQualidade } from '@/types';

const base = 'certificados-qualidade/';

export type PreencherPorNFePayload = {
  nf_saida_id?: number;
  nf_saida_historica_id?: number;
};

export type PreencherPorNFeResponse = Partial<CertificadoQualidade> & {
  mensagens?: string[];
};

async function extractPdfErrorMessage(error: unknown, fallback: string): Promise<string> {
  const ax = error as AxiosError<Blob | unknown>;
  const blob = ax.response?.data;
  if (blob instanceof Blob) {
    try {
      const text = await blob.text();
      if (text) {
        try {
          const parsed = JSON.parse(text) as { detail?: string };
          if (parsed?.detail) return parsed.detail;
        } catch {
          if (text.trim().startsWith('<')) return fallback;
          return text;
        }
      }
    } catch {
      return fallback;
    }
  }
  return apiErrorMessage(error, { fallback });
}

function sanitizeFilenamePart(value?: string): string {
  return (value || '')
    .trim()
    .replace(/[\\/:*?"<>|]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeCertNumber(value?: string): string {
  let normalized = sanitizeFilenamePart(value)
    .replace(/[\\\s]+/g, '')
    .replace(/[^A-Za-z0-9-]/g, '')
    .toUpperCase();
  normalized = normalized.replace(/-/g, '');
  while (normalized.startsWith('CQCQ')) normalized = normalized.slice(2);
  if (!normalized) return '';
  if (!normalized.startsWith('CQ')) normalized = `CQ${normalized}`;
  return normalized.replace(/\//g, '');
}

function shortClientName(value?: string): string {
  let v = sanitizeFilenamePart(value).toUpperCase();
  if (!v) return 'CLIENTE';
  v = v
    .replace(/\b(LTDA|EIRELI|S\/A|SA|ME|EPP)\b/g, ' ')
    .replace(/\b(PESADA|INDUSTRIAL|INDUSTRIA|COMERCIO|COMERCIAL)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return (v || 'CLIENTE').slice(0, 40).trim();
}

function normalizeNf(value?: string): string {
  const clean = sanitizeFilenamePart(value);
  const digits = clean.replace(/\D+/g, '');
  if (digits && digits.length <= 12) return digits.padStart(6, '0');
  return clean.replace(/[^\w.-]+/g, '').slice(0, 20) || 'SEMNF';
}

type PdfFilenameInput = {
  numero?: string;
  cliente?: string;
  nf?: string;
};

function buildPdfFilename(input: PdfFilenameInput, preview: boolean): string {
  const cert = normalizeCertNumber(input.numero) || 'SEMNUMERO';
  const cliente = shortClientName(input.cliente);
  const nf = normalizeNf(input.nf);
  const baseName = `CERTIFICADO DE QUALIDADE - ${cert} - ${cliente} - NF-e ${nf}`;
  return preview
    ? `${baseName} - PREVIA.pdf`
    : `${baseName}.pdf`;
}

async function getPdfBlob(id: number, preview = false): Promise<Blob> {
  try {
    const resp = await api.get<Blob>(`${base}${id}/pdf/`, {
      params: preview ? { preview: 'true' } : undefined,
      responseType: 'blob',
    });
    const contentType = resp.headers['content-type'] || '';
    if (!contentType.includes('application/pdf')) {
      throw new Error('Resposta inválida do servidor ao gerar PDF.');
    }
    return new Blob([resp.data], { type: 'application/pdf' });
  } catch (error) {
    const message = await extractPdfErrorMessage(
      error,
      'Não foi possível gerar o PDF. Verifique se o certificado foi salvo como rascunho.',
    );
    throw new Error(message);
  }
}

export const certificadosQualidadeService = {
  getAll: async () => (await api.get<CertificadoQualidade[]>(base)).data,
  getById: async (id: number) => (await api.get<CertificadoQualidade>(`${base}${id}/`)).data,
  create: async (payload: Omit<CertificadoQualidade, 'id' | 'criado_em' | 'atualizado_em' | 'numero_formatado'>) =>
    (await api.post<CertificadoQualidade>(base, payload)).data,
  update: async (id: number, payload: Partial<CertificadoQualidade>) =>
    (await api.patch<CertificadoQualidade>(`${base}${id}/`, payload)).data,
  preencherPorNfe: async (payload: PreencherPorNFePayload) =>
    (await api.post<PreencherPorNFeResponse>(`${base}preencher-por-nfe/`, payload)).data,
  corridasDisponiveisPorProduto: async (produtoId: number) =>
    (await api.get<CorridaDisponivelCertificadoQualidade[]>(`${base}corridas-disponiveis/`, { params: { produto_id: produtoId } })).data,
  obterPdfBlob: async (id: number, preview = false) => getPdfBlob(id, preview),
  buildPdfFilename,
  visualizarPdf: async (id: number, preview = false, input?: PdfFilenameInput) => {
    const blob = await getPdfBlob(id, preview);
    const objectUrl = URL.createObjectURL(blob);
    const win = window.open(objectUrl, '_blank', 'noopener,noreferrer');
    if (!win) {
      const shouldDownload = window.confirm(
        'O navegador bloqueou a abertura da prévia em nova aba. Deseja baixar o PDF agora?',
      );
      if (shouldDownload) {
        const a = document.createElement('a');
        a.href = objectUrl;
        a.download = buildPdfFilename(input || {}, preview);
        a.click();
      } else {
        URL.revokeObjectURL(objectUrl);
        throw new Error('A abertura da prévia foi bloqueada pelo navegador.');
      }
    }
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  },
  baixarPdf: async (id: number, preview = false, input?: PdfFilenameInput) => {
    const blob = await getPdfBlob(id, preview);
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = buildPdfFilename(input || {}, preview);
    a.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
  },
};
