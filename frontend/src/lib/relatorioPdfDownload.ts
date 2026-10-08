import { isAxiosError, type AxiosError } from 'axios';
import api from '@/services/api/config';
import { relatorioFiltrosToQuery, type RelatorioFiltrosState } from '@/lib/relatorioFinanceiro';

export const MSG_ERRO_PDF_RELATORIO =
  'Não foi possível gerar o PDF do relatório. Tente novamente.';

export type RelatorioPdfEndpoint =
  | 'contas-receber'
  | 'contas-pagar'
  | 'fluxo-previsto'
  | 'categorias'
  | 'clientes'
  | 'fornecedores';

const FILE_PREFIX: Record<RelatorioPdfEndpoint, string> = {
  'contas-receber': 'relatorio-contas-a-receber',
  'contas-pagar': 'relatorio-contas-a-pagar',
  'fluxo-previsto': 'fluxo-previsto',
  categorias: 'receitas-despesas-categoria',
  clientes: 'relatorio-por-cliente',
  fornecedores: 'relatorio-por-fornecedor',
};

function pdfFilename(endpoint: RelatorioPdfEndpoint): string {
  const d = new Date().toISOString().slice(0, 10);
  return `${FILE_PREFIX[endpoint]}-${d}.pdf`;
}

export async function fetchRelatorioFinanceiroPdf(
  endpoint: RelatorioPdfEndpoint,
  filtros: RelatorioFiltrosState,
): Promise<Blob> {
  const q = relatorioFiltrosToQuery(filtros);
  const res = await api.get(`financeiro/relatorios/${endpoint}/pdf/`, {
    params: { ...q, _: Date.now() },
    responseType: 'blob',
    // DRF só negocia JSON por padrão; application/pdf retorna 406 (igual PDFs comerciais).
    headers: { Accept: '*/*', 'Cache-Control': 'no-cache' },
  });
  const raw = res.data as Blob;
  const headBuf = await raw.slice(0, Math.min(12, raw.size)).arrayBuffer();
  const head = new TextDecoder('utf-8', { fatal: false }).decode(headBuf).trimStart();
  if (!head.startsWith('%PDF')) {
    if (head.startsWith('{')) {
      try {
        const j = JSON.parse(await raw.text()) as { detail?: string };
        const d = typeof j.detail === 'string' ? j.detail : '';
        throw new Error(d || MSG_ERRO_PDF_RELATORIO);
      } catch (e) {
        if (e instanceof Error && e.message !== MSG_ERRO_PDF_RELATORIO) throw e;
      }
    }
    throw new Error(MSG_ERRO_PDF_RELATORIO);
  }
  return raw;
}

export function openRelatorioPdfBlob(blob: Blob, endpoint: RelatorioPdfEndpoint): void {
  const filename = pdfFilename(endpoint);
  const file = new File([blob], filename, { type: 'application/pdf' });
  const url = URL.createObjectURL(file);
  const tab = window.open(url, '_blank');
  if (!tab) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 300_000);
}

export async function gerarRelatorioFinanceiroPdf(
  endpoint: RelatorioPdfEndpoint,
  filtros: RelatorioFiltrosState,
): Promise<void> {
  try {
    const blob = await fetchRelatorioFinanceiroPdf(endpoint, filtros);
    openRelatorioPdfBlob(blob, endpoint);
  } catch (e) {
    if (e instanceof Error && !isAxiosError(e)) throw e;
    const ax = e as AxiosError<Blob>;
    if (ax.response?.status === 401) {
      throw new Error('Sessão expirada. Faça login novamente.');
    }
    if (ax.response?.status === 406) {
      throw new Error(MSG_ERRO_PDF_RELATORIO);
    }
    const data = ax.response?.data;
    if (data instanceof Blob) {
      try {
        const t = await data.text();
        if (t.trimStart().startsWith('{')) {
          const j = JSON.parse(t) as { detail?: string };
          if (typeof j.detail === 'string' && j.detail) throw new Error(j.detail);
        }
      } catch (inner) {
        if (inner instanceof Error && inner.message !== MSG_ERRO_PDF_RELATORIO) throw inner;
      }
    }
    throw new Error(MSG_ERRO_PDF_RELATORIO);
  }
}
