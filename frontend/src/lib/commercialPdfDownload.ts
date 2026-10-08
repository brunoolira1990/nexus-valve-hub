import { isAxiosError, type AxiosError } from 'axios';
import api from '@/services/api/config';

export type CommercialPdfDocConfig = {
  apiBasePath: string;
  filePrefix: string;
  docTitle: string;
  headerLabel: string;
  notFoundMessage: string;
};

export const MSG_SALVE_ANTES_PDF = 'Salve antes de gerar PDF.';

const PREVIEW_SAVE_HINT =
  'Para salvar com o nome correto, use o botão Baixar PDF desta tela. O visualizador do navegador pode usar um nome aleatório ao salvar o PDF em blob.';

function escHtmlAttr(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Sanitiza referência (número ou id) para nome de arquivo PDF comercial. */
export function buildPdfFilename(prefix: string, numeroRef: string, id: number): string {
  const raw = (numeroRef || '').trim() || String(id);
  const safe =
    raw
      .replace(/[/\\]+/g, '-')
      .replace(/\s+/g, '')
      .replace(/[^\w.-]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-+|-+$/g, '') || String(id);
  return `${prefix}-${safe}.pdf`;
}

/** @deprecated use buildPdfFilename */
export const commercialPdfFilename = buildPdfFilename;

function writeCommercialPdfPreviewTab(
  tab: Window,
  blobUrl: string,
  filename: string,
  tabTitle: string,
  headerLine: string,
): void {
  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>${escHtmlAttr(tabTitle)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body { margin: 0; height: 100%; display: flex; flex-direction: column; font-family: system-ui, -apple-system, Segoe UI, sans-serif; }
    header { flex: 0 0 auto; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 12px; padding: 10px 16px; background: #0f172a; color: #f8fafc; border-bottom: 1px solid #334155; }
    header .title { font-size: 14px; font-weight: 600; }
    header .hint { flex: 1 1 100%; margin: 0; font-size: 11px; line-height: 1.35; color: #94a3b8; font-weight: 400; }
    @media (min-width: 640px) { header .hint { flex: 1 1 auto; order: 2; } header .title { order: 1; } header .download { order: 3; } }
    header a.download { color: #93c5fd; font-weight: 600; text-decoration: none; white-space: nowrap; }
    header a.download:hover { text-decoration: underline; }
    main { flex: 1 1 auto; min-height: 0; background: #1e293b; }
    iframe { width: 100%; height: 100%; border: none; display: block; background: #fff; }
  </style>
</head>
<body>
  <header>
    <span class="title">${escHtmlAttr(headerLine)}</span>
    <p class="hint">${escHtmlAttr(PREVIEW_SAVE_HINT)}</p>
    <a class="download" href="${blobUrl}" download="${escHtmlAttr(filename)}">Baixar PDF</a>
  </header>
  <main><iframe src="${blobUrl}" title="${escHtmlAttr(tabTitle)}"></iframe></main>
</body>
</html>`;
  tab.document.open();
  tab.document.write(html);
  tab.document.close();
}

export async function fetchCommercialPdfBlob(
  config: CommercialPdfDocConfig,
  id: number,
  invalidIdMessage?: string,
): Promise<Blob> {
  const nid = Number(id);
  if (!Number.isFinite(nid) || nid <= 0) {
    throw new Error(invalidIdMessage ?? config.notFoundMessage);
  }
  const res = await api.get(`${config.apiBasePath}${nid}/pdf/`, {
    responseType: 'blob',
    headers: { Accept: '*/*', 'Cache-Control': 'no-cache' },
    params: { _: Date.now() },
  });
  const raw = res.data as Blob;
  const headBuf = await raw.slice(0, Math.min(12, raw.size)).arrayBuffer();
  const head = new TextDecoder('utf-8', { fatal: false }).decode(headBuf).trimStart();
  if (!head.startsWith('%PDF')) {
    if (head.startsWith('{')) {
      let j: { detail?: string };
      try {
        j = JSON.parse(await raw.text()) as { detail?: string };
      } catch {
        throw new Error('Resposta inválida ao gerar o PDF.');
      }
      const d = typeof j.detail === 'string' ? j.detail : '';
      if (d.toLowerCase().includes('credenciais') || d.toLowerCase().includes('autenticação')) {
        throw new Error(
          'Sessão inválida ou não autenticado. Faça login novamente e use «Visualizar PDF» no sistema. ' +
            'Abrir a URL da API direto no navegador não envia o token JWT.',
        );
      }
      throw new Error(d || 'Resposta inesperada ao gerar o PDF.');
    }
    if (head.startsWith('<')) {
      throw new Error(
        'A resposta não é um PDF (recebeu HTML). Use «Visualizar PDF» ou «Baixar PDF» dentro do sistema com sessão ativa.',
      );
    }
    if (raw.size === 0) {
      throw new Error('O servidor devolveu conteúdo vazio em vez do PDF.');
    }
  }
  return raw;
}

export function downloadPdfBlob(blob: Blob, filename: string): void {
  const pdfFile = new File([blob], filename, { type: 'application/pdf' });
  const blobUrl = URL.createObjectURL(pdfFile);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(blobUrl), 120_000);
}

export async function mensagemErroCommercialPdf(err: unknown, fallback: string): Promise<string> {
  const ax = err as AxiosError<Blob>;
  const status = ax.response?.status;
  if (status === 401) {
    return 'Não foi possível autenticar para gerar o PDF. Faça login novamente.';
  }
  if (status === 403) {
    return 'Você não tem permissão para gerar este PDF.';
  }
  if (status === 404) {
    return fallback;
  }
  const data = ax.response?.data;
  if (data instanceof Blob) {
    try {
      const ct = String(ax.response?.headers?.['content-type'] ?? '');
      if (ct.includes('application/json') || data.type?.includes('json')) {
        const t = await data.text();
        const j = JSON.parse(t) as { detail?: string };
        if (typeof j.detail === 'string') return j.detail;
      }
    } catch {
      /* ignore */
    }
  }
  if (err instanceof Error && !isAxiosError(err)) return err.message;
  return fallback;
}

export async function visualizarCommercialPdf(
  config: CommercialPdfDocConfig,
  id: number,
  numeroRef: string,
  previewTab?: Window | null,
  invalidIdMessage?: string,
): Promise<void> {
  try {
    const raw = await fetchCommercialPdfBlob(config, id, invalidIdMessage);
    const nid = Number(id);
    const filename = buildPdfFilename(config.filePrefix, numeroRef, nid);
    const pdfFile = new File([raw], filename, { type: 'application/pdf' });
    const blobUrl = URL.createObjectURL(pdfFile);
    const numLabel = (numeroRef || String(nid)).trim();
    const tabTitle = `${config.docTitle} ${numLabel} · NEXUS APP`;
    const headerLine = `${config.headerLabel} · ${numLabel}`;

    const openPreview = (w: Window) => {
      try {
        w.opener = null;
      } catch {
        /* ignore */
      }
      writeCommercialPdfPreviewTab(w, blobUrl, filename, tabTitle, headerLine);
    };

    if (previewTab && !previewTab.closed) {
      openPreview(previewTab);
    } else {
      const novaAba = window.open('', '_blank');
      if (novaAba) {
        openPreview(novaAba);
      } else {
        alert(
          'O navegador bloqueou a nova aba com o PDF. Permita pop-ups ou use «Baixar PDF».',
        );
        downloadPdfBlob(raw, filename);
      }
    }
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 300_000);
  } catch (e) {
    if (e instanceof Error && !isAxiosError(e)) throw e;
    throw new Error(await mensagemErroCommercialPdf(e, config.notFoundMessage));
  }
}

/** @deprecated use visualizarCommercialPdf */
export const gerarCommercialPdf = visualizarCommercialPdf;

export async function baixarCommercialPdf(
  config: CommercialPdfDocConfig,
  id: number,
  numeroRef: string,
  invalidIdMessage?: string,
): Promise<void> {
  try {
    const raw = await fetchCommercialPdfBlob(config, id, invalidIdMessage);
    const nid = Number(id);
    const filename = buildPdfFilename(config.filePrefix, numeroRef, nid);
    downloadPdfBlob(raw, filename);
  } catch (e) {
    if (e instanceof Error && !isAxiosError(e)) throw e;
    throw new Error(await mensagemErroCommercialPdf(e, config.notFoundMessage));
  }
}

export const PROPOSTA_PDF_CONFIG: CommercialPdfDocConfig = {
  apiBasePath: 'propostas/',
  filePrefix: 'proposta',
  docTitle: 'Proposta Comercial',
  headerLabel: 'Proposta Comercial',
  notFoundMessage: 'Proposta não encontrada para geração do PDF.',
};

export const PEDIDO_VENDA_PDF_CONFIG: CommercialPdfDocConfig = {
  apiBasePath: 'pedidos-venda/',
  filePrefix: 'pedido-venda',
  docTitle: 'Pedido de Venda',
  headerLabel: 'Pedido de Venda',
  notFoundMessage: 'Pedido de venda não encontrado para geração do PDF.',
};

export const PEDIDO_COMPRA_PDF_CONFIG: CommercialPdfDocConfig = {
  apiBasePath: 'pedidos-compra/',
  filePrefix: 'pedido-compra',
  docTitle: 'Pedido de Compra',
  headerLabel: 'Pedido de Compra',
  notFoundMessage: 'Pedido de compra não encontrado para geração do PDF.',
};
