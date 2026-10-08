/** Download e visualização de arquivos binários (XML/PDF) via Blob — com auth axios. */

export function parseContentDispositionFilename(header: string | undefined | null): string | null {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;\n]+)/i.exec(header);
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      return utf8[1];
    }
  }
  const quoted = /filename="([^"]+)"/i.exec(header);
  if (quoted?.[1]) return quoted[1];
  const plain = /filename=([^;\n]+)/i.exec(header);
  return plain?.[1]?.trim().replace(/^"|"$/g, '') || null;
}

export async function readBlobErrorMessage(blob: Blob, fallback: string): Promise<string> {
  try {
    const text = await blob.text();
    const json = JSON.parse(text) as {
      mensagem?: string;
      detail?: string;
      mensagens?: string[];
    };
    return (
      json.mensagem ||
      json.detail ||
      (Array.isArray(json.mensagens) ? json.mensagens[0] : undefined) ||
      fallback
    );
  } catch {
    return fallback;
  }
}

export class PopupBlockedError extends Error {
  constructor(
    message = 'O navegador bloqueou a nova aba. Libere pop-ups para visualizar o DANFE.',
  ) {
    super(message);
    this.name = 'PopupBlockedError';
  }
}

export function ensurePdfBlob(blob: Blob): Blob {
  if (!blob?.size) {
    throw new Error('O PDF retornado está vazio.');
  }
  if (blob.type === 'application/pdf') {
    return blob;
  }
  return new Blob([blob], { type: 'application/pdf' });
}

export function downloadBlobFile(blob: Blob, filename: string) {
  const pdfBlob = blob.type.includes('pdf') ? ensurePdfBlob(blob) : blob;
  if (!pdfBlob?.size) {
    throw new Error('O arquivo retornado está vazio.');
  }
  const url = URL.createObjectURL(pdfBlob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

/**
 * Abre PDF em nova aba sem iniciar download.
 *
 * 1. Abre a aba de forma síncrona no clique (`window.open('', '_blank')`).
 * 2. Busca o Blob com autenticação.
 * 3. Atribui `location.href` à blob URL (não usa `download`, não usa `location.replace`).
 * 4. Só revoga a URL após delay longo (padrão 60s), para o Chrome carregar o PDF.
 */
export async function visualizarPdfEmNovaAba(
  fetchBlob: () => Promise<Blob>,
  options?: { revokeMs?: number },
): Promise<void> {
  const novaAba = window.open('', '_blank');
  if (!novaAba) {
    throw new PopupBlockedError();
  }

  try {
    try {
      novaAba.document.title = 'Carregando DANFE…';
      novaAba.document.body.textContent = 'Carregando PDF…';
    } catch {
      /* ignore — about:blank pode restringir escrita em alguns casos */
    }

    const rawBlob = await fetchBlob();
    const pdfBlob = ensurePdfBlob(rawBlob);
    if (!pdfBlob.size) {
      throw new Error('O PDF retornado está vazio.');
    }

    const blobUrl = URL.createObjectURL(pdfBlob);
    novaAba.location.href = blobUrl;
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), options?.revokeMs ?? 60_000);
  } catch (error) {
    try {
      novaAba.close();
    } catch {
      /* ignore */
    }
    throw error;
  }
}

/** @deprecated Preferir visualizarPdfEmNovaAba para PDFs. */
export function openBlobInNewTab(blob: Blob, filename = 'documento.pdf') {
  void filename;
  const pdfBlob = blob.type.includes('pdf') ? ensurePdfBlob(blob) : blob;
  const url = URL.createObjectURL(pdfBlob);
  const opened = window.open(url, '_blank');
  if (!opened) {
    URL.revokeObjectURL(url);
    throw new PopupBlockedError();
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}
