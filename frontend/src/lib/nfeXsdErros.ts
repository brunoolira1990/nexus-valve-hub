export type NFeXsdErro = {
  linha?: number;
  coluna?: number;
  elemento?: string;
  mensagem?: string;
  message?: string;
  contexto?: string;
  tipo?: string;
  dominio?: string;
};

export type NFeRespostaValidacaoXsd = {
  erros?: NFeXsdErro[];
  erros_xsd?: NFeXsdErro[];
  validacao_xsd?: { erros?: NFeXsdErro[]; tipo?: string; ok?: boolean };
  erros?: unknown[];
  etapa?: string;
  mensagem?: string;
  sefaz_transmitida?: boolean;
};

const CONTEXT_LABELS: Record<string, string> = {
  XML_ASSINADO: 'XML assinado',
  ENVI_NFE: 'enviNFe',
  XML_PRE: 'XML preliminar',
  NFE: 'XML NF-e',
  CARACTERES_EDICAO: 'Caracteres de edição',
};

function labelContexto(contexto?: string): string {
  const ctx = (contexto || '').trim();
  if (!ctx) return '';
  return CONTEXT_LABELS[ctx] || ctx.replace(/_/g, ' ');
}

function tagDoElemento(elemento?: string): string {
  const texto = (elemento || '').trim().replace(/\/$/, '');
  if (!texto) return '';
  const ultimo = texto.split('/').pop() || '';
  const idx = ultimo.indexOf('}');
  return idx >= 0 ? ultimo.slice(idx + 1) : ultimo;
}

export function formatNfeXsdErro(erro: unknown): string {
  if (typeof erro === 'string') return erro.trim();
  if (!erro || typeof erro !== 'object') return '';
  const o = erro as NFeXsdErro;
  const contexto = labelContexto(o.contexto || o.tipo);
  const tag = tagDoElemento(o.elemento);
  const mensagem = (o.mensagem || o.message || '').trim();
  const linha = o.linha ?? 0;
  const coluna = o.coluna ?? 0;

  const partes: string[] = [];
  if (contexto) partes.push(contexto);
  if (tag) partes.push(`Tag ${tag}`);
  if (mensagem) partes.push(mensagem);
  if (linha || coluna) {
    const loc: string[] = [];
    if (linha) loc.push(`linha ${linha}`);
    if (coluna) loc.push(`coluna ${coluna}`);
    partes.push(`(${loc.join(' · ')})`);
  }
  if (!partes.length) return mensagem || 'Erro XSD desconhecido.';
  if (partes.length <= 2) return partes.join(': ');
  return `${partes[0]}: ${partes[1]} — ${partes.slice(2).join(' ')}`;
}

export function formatNfeErrosLista(erros: unknown[] | undefined | null): string {
  if (!erros?.length) return '';
  return erros.map(formatNfeXsdErro).filter(Boolean).join(' · ');
}

export function extrairErrosXsd(res: NFeRespostaValidacaoXsd | null | undefined): NFeXsdErro[] {
  if (!res) return [];
  if (Array.isArray(res.erros_xsd) && res.erros_xsd.length) return res.erros_xsd;
  const vx = res.validacao_xsd?.erros;
  if (Array.isArray(vx) && vx.length) return vx;
  if (Array.isArray(res.erros) && res.erros.some((e) => e && typeof e === 'object')) {
    return res.erros.filter((e) => e && typeof e === 'object') as NFeXsdErro[];
  }
  return [];
}

export function mensagemEmissaoComErrosXsd(
  res: NFeRespostaValidacaoXsd,
  fallback = 'Emissão não concluída.',
): string {
  const errosXsd = extrairErrosXsd(res);
  const errosTxt = errosXsd.length
    ? formatNfeErrosLista(errosXsd)
    : formatNfeErrosLista(res.erros);
  const msgBase = res.mensagem || errosTxt || fallback;
  const etapaTxt = res.etapa ? `Etapa: ${res.etapa}. ` : '';
  if (errosTxt && !msgBase.includes(errosTxt)) {
    return `${etapaTxt}${msgBase} (${errosTxt})`.trim();
  }
  return `${etapaTxt}${msgBase}`.trim();
}
