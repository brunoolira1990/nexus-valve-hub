import type { AxiosError } from 'axios';

const FIELD_LABELS: Record<string, string> = {
  numero_certificado_fornecedor: 'número do certificado fornecedor',
  numero_certificado_fornecedor_item: 'número do certificado fornecedor do item',
  numero_certificado_fornecedor_componente: 'número do certificado fornecedor do componente',
  corrida: 'corrida/lote',
  lote: 'lote',
  norma: 'norma',
  composicao_json: 'composição química',
  ensaio_tracao_json: 'tração / propriedades mecânicas',
  ensaio_impacto_json: 'impacto',
  componentes: 'componentes',
  itens: 'itens',
  fornecedor: 'fornecedor',
  fornecedor_nome_snapshot: 'fornecedor',
  nf_entrada_historica: 'NF-e de entrada histórica',
  nf_entrada_operacional: 'NF-e de entrada operacional',
  numero_nf_entrada: 'NF-e de entrada',
  detail: 'certificado',
};

const GENERIC_FALLBACK = 'Não foi possível concluir a operação. Verifique os dados e tente novamente.';

function cleanMessage(value: string): string {
  return String(value).replace(/\s+/g, ' ').replace(/\[object Object\]/gi, '').trim();
}

function mapFieldLabel(field: string): string {
  return FIELD_LABELS[field] || field.replace(/_/g, ' ');
}

function normalizeFieldSentence(field: string, message: string): string {
  const m = cleanMessage(message);
  if (!m) return '';
  const lower = m.toLowerCase();
  const label = mapFieldLabel(field);
  if (lower.includes('este campo') && lower.includes('obrigat')) return `informe ${label}.`;
  if (lower.includes('informe')) return m.endsWith('.') ? m : `${m}.`;
  return `${label}: ${m}`;
}

function extractData(error: unknown): unknown {
  const ax = error as AxiosError<unknown>;
  return ax?.response?.data ?? error;
}

type PathCtx = { itemIdx?: number; compIdx?: number; compName?: string };

function prefixWithContext(msg: string, ctx: PathCtx): string {
  let prefix = '';
  if (ctx.itemIdx != null) prefix = `Item ${ctx.itemIdx + 1}`;
  if (ctx.compIdx != null) {
    const compLabel = ctx.compName?.trim() ? `Componente ${ctx.compName.trim()}` : `Componente ${ctx.compIdx + 1}`;
    prefix = prefix ? `${prefix} > ${compLabel}` : compLabel;
  }
  if (!prefix) return msg;
  const normalized = msg.charAt(0).toLowerCase() + msg.slice(1);
  return `${prefix}: ${normalized}`;
}

function walk(node: unknown, out: string[], ctx: PathCtx = {}): void {
  if (node == null) return;
  if (typeof node === 'string' || typeof node === 'number' || typeof node === 'boolean') {
    const msg = cleanMessage(String(node));
    if (msg) out.push(prefixWithContext(msg, ctx));
    return;
  }

  if (Array.isArray(node)) {
    if (node.every((v) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')) {
      for (const v of node) walk(String(v), out, ctx);
      return;
    }
    node.forEach((entry, idx) => {
      const nextCtx = { ...ctx };
      if (ctx.itemIdx != null && ctx.compIdx == null) nextCtx.compIdx = idx;
      walk(entry, out, nextCtx);
    });
    return;
  }

  if (typeof node === 'object') {
    const obj = node as Record<string, unknown>;
    for (const [key, value] of Object.entries(obj)) {
      if (key === 'itens' && Array.isArray(value)) {
        value.forEach((entry, itemIdx) => walk(entry, out, { ...ctx, itemIdx }));
        continue;
      }
      if (key === 'componentes' && Array.isArray(value)) {
        value.forEach((entry, compIdx) => {
          const compObj = entry && typeof entry === 'object' ? (entry as Record<string, unknown>) : {};
          const compName = String(
            compObj.__nome_componente || compObj.nome_componente || compObj.descricao_componente || '',
          ).trim();
          walk(entry, out, { ...ctx, compIdx, compName });
        });
        continue;
      }
      if (key === '__nome_componente') continue;

      if (Array.isArray(value)) {
        if (value.every((v) => typeof v === 'string')) {
          value.forEach((m) => {
            const sentence = normalizeFieldSentence(key, String(m));
            if (sentence) out.push(prefixWithContext(sentence, ctx));
          });
          continue;
        }
        walk(value, out, ctx);
        continue;
      }

      if (typeof value === 'string') {
        const sentence = key === 'detail'
          ? cleanMessage(value)
          : normalizeFieldSentence(key, value);
        if (sentence) out.push(prefixWithContext(sentence, ctx));
        continue;
      }

      walk(value, out, ctx);
    }
  }
}

export function formatApiErrors(error: unknown): string[] {
  const data = extractData(error);
  const out: string[] = [];
  walk(data, out, {});
  const normalized = Array.from(
    new Set(
      out
        .map((m) => cleanMessage(m))
        .filter((m) => m && !/\[object object\]/i.test(m)),
    ),
  );
  return normalized.length ? normalized : [GENERIC_FALLBACK];
}

