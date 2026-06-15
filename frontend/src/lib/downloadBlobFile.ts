/** Download de arquivos binários (XML/PDF) via Blob — com auth axios. */

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

export function downloadBlobFile(blob: Blob, filename: string) {
  if (!blob?.size) {
    throw new Error('O arquivo retornado está vazio.');
  }
  const url = URL.createObjectURL(blob);
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

export function openBlobInNewTab(blob: Blob) {
  if (!blob?.size) {
    throw new Error('O arquivo retornado está vazio.');
  }
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
