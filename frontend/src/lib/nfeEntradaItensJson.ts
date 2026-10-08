/** Item parseado do XML de NF-e de entrada (campo `itens_json` da API). */

export type NFeEntradaItemJsonRaw = {
  n_item?: number | string;
  nItem?: number | string;
  prod?: Record<string, unknown>;
  imposto?: Record<string, unknown>;
};

export type NFeEntradaItemXmlResumo = {
  numeroItem: string;
  codigoProduto: string;
  descricao: string;
  ncm: string;
  cfop: string;
  unidade: string;
  quantidade: number | null;
  valorUnitario: number | null;
  valorTotal: number | null;
};

function str(v: unknown): string {
  if (v === null || v === undefined) return '';
  return String(v).trim();
}

function num(v: unknown): number | null {
  const s = str(v);
  if (!s) return null;
  const n = Number(s.replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

function prodField(prod: Record<string, unknown> | undefined, key: string): string {
  return str(prod?.[key]);
}

export function numeroItemNfeEntradaJson(raw: NFeEntradaItemJsonRaw, index: number): string {
  const n = str(raw.n_item) || str(raw.nItem);
  return n || String(index + 1);
}

/** Normaliza um item de `itens_json` para exibição read-only na revisão. */
export function mapItemNfeEntradaJson(raw: unknown, index: number): NFeEntradaItemXmlResumo {
  const r = (raw && typeof raw === 'object' ? raw : {}) as NFeEntradaItemJsonRaw;
  const prod = r.prod && typeof r.prod === 'object' ? r.prod : {};
  return {
    numeroItem: numeroItemNfeEntradaJson(r, index),
    codigoProduto: prodField(prod, 'cProd'),
    descricao: prodField(prod, 'xProd') || '—',
    ncm: prodField(prod, 'NCM'),
    cfop: prodField(prod, 'CFOP'),
    unidade: prodField(prod, 'uCom'),
    quantidade: num(prod.qCom),
    valorUnitario: num(prod.vUnCom),
    valorTotal: num(prod.vProd),
  };
}

export function mapItensNfeEntradaJson(itensJson: unknown): NFeEntradaItemXmlResumo[] {
  if (!Array.isArray(itensJson)) return [];
  return itensJson.map((raw, index) => mapItemNfeEntradaJson(raw, index));
}

export function temItensXmlNfeEntrada(nfe: {
  itens?: unknown[];
  itens_json?: unknown;
}): boolean {
  return mapItensNfeEntradaJson(nfe.itens_json).length > 0;
}

export function temItensOperacionaisNfeEntrada(nfe: { itens?: unknown[] }): boolean {
  return Array.isArray(nfe.itens) && nfe.itens.length > 0;
}
