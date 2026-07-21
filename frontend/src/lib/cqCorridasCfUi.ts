/**
 * Hotfix CQ — múltiplas corridas do Certificado de Fornecedor como itens irmãos.
 *
 * O item do CQ já vinculado a um CF/item exato pode ser desdobrado em uma linha
 * por corrida (principal + adicionais do item exato do CF):
 * - quantidade específica por corrida, distribuindo exatamente o total original;
 * - dados técnicos por linha: herdados da origem OU próprios (vazios, para preencher);
 * - origem documental preservada (CF, item do CF, corrida, lote, NF-e de entrada).
 *
 * Nada aqui altera estoque, alocação ou documentos fiscais; a origem física
 * não é comprovada nesta etapa.
 */

import { chaveCorridaLoteNormalizada } from '@/lib/cfCorridasAdicionaisUi';
import type { ItemCertificadoQualidade } from '@/types';

export const TITULO_MODAL_CORRIDAS_CF_CQ = 'Adicionar corridas do Certificado de Fornecedor';
export const MSG_ORIGEM_DOCUMENTAL_NAO_FISICA_CQ =
  'A origem documental foi identificada. A origem física no estoque/alocação não é comprovada nesta etapa.';
export const MSG_SELECIONE_CORRIDAS_CF_CQ = 'Selecione ao menos uma corrida para aplicar.';
export const MSG_QUANTIDADE_CORRIDA_OBRIGATORIA_CQ =
  'Informe quantidade maior que zero para cada corrida selecionada.';
export const MSG_SOMA_EXCEDE_TOTAL_CQ =
  'A soma das quantidades das corridas excede a quantidade do item original.';
export const MSG_SOMA_DIFERENTE_TOTAL_CQ =
  'Para aplicar, a soma das quantidades deve ser igual à quantidade do item original.';
export const MSG_ORIGEM_DUPLICADA_CQ = 'A mesma corrida/origem não pode ser adicionada duas vezes.';
export const MSG_DADOS_PROPRIOS_PENDENTES_CQ =
  'Corrida com dados técnicos próprios: preencha composição, propriedades e ensaios antes de emitir.';
export const MSG_DADOS_PROPRIOS_MANUAIS_CQ =
  'A corrida está vinculada documentalmente ao CF, mas os dados técnicos desta linha serão preenchidos manualmente.';

export const ORIGEM_STATUS_TECNICO_HERDADO_CF = 'dados_tecnicos_herdados_cf';
export const ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES = 'dados_tecnicos_manuais_pendentes';

/**
 * O backend normaliza campos operacionais para maiúsculas ao salvar; após um
 * save→reload o status volta como 'DADOS_TECNICOS_...'. A comparação precisa
 * ser insensível a caixa para não reclassificar linhas manuais como herdadas.
 */
const statusTecnicoNormalizado = (item: ItemCertificadoQualidade): string =>
  String(item.origem_status_tecnico || '').trim().toLowerCase();

const statusTecnicoClassificado = (item: ItemCertificadoQualidade): boolean =>
  [
    ORIGEM_STATUS_TECNICO_HERDADO_CF,
    ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES,
  ].includes(statusTecnicoNormalizado(item));

export type CorridaCfParaCq = {
  chave_origem: string;
  tipo_linha: 'corrida_principal' | 'corrida_adicional';
  corrida: string;
  lote: string;
  quantidade_no_certificado: string | null;
  unidade: string;
  origem_tecnica: string;
  origem_tecnica_label: string;
  dados_tecnicos_herdados: boolean;
  permite_preenchimento_manual: boolean;
  modo_dados_tecnicos_padrao: 'herdados';
  modos_dados_tecnicos_permitidos: Array<'herdados' | 'manual'>;
  certificado_fornecedor_id: number;
  item_certificado_fornecedor_id: number;
  codigo_produto: string;
  descricao_material: string;
  fornecedor_nome: string;
  numero_nf_entrada: string;
  numero_certificado_fornecedor: string;
  status_certificado_fornecedor: string;
  dados_tecnicos: {
    norma: string;
    ncm: string;
    tipo_dados_tecnicos: string;
    composicao_json: Record<string, unknown>;
    ensaio_tracao_json: Record<string, unknown>;
    ensaio_impacto_json: Record<string, unknown>;
  };
};

export type CorridasCfParaCqResponse = {
  linhas: CorridaCfParaCq[];
  avisos: string[];
  mensagem_origem_fisica: string;
  limitacao_itens_independentes: string;
};

export type ModoDadosTecnicosCorridaCq = 'herdados' | 'proprios';

export type SelecaoCorridaCfCq = {
  linha: CorridaCfParaCq;
  quantidade: string;
  dadosTecnicos: ModoDadosTecnicosCorridaCq;
};

const parseQuantidade = (raw: string): number | null => {
  const v = String(raw ?? '').trim().replace(',', '.');
  if (!v) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export type ResumoDistribuicaoCorridasCq = {
  quantidadeTotal: number;
  totalDistribuido: number;
  saldoRestante: number;
};

export function resumoDistribuicaoCorridasCfCq(
  quantidadeTotal: number,
  selecoes: SelecaoCorridaCfCq[],
): ResumoDistribuicaoCorridasCq {
  const totalDistribuido = selecoes.reduce((acc, s) => {
    const n = parseQuantidade(s.quantidade);
    return acc + (n != null && n > 0 ? n : 0);
  }, 0);
  const arred = (v: number) => Math.round(v * 1000) / 1000;
  return {
    quantidadeTotal: arred(quantidadeTotal),
    totalDistribuido: arred(totalDistribuido),
    saldoRestante: arred(quantidadeTotal - totalDistribuido),
  };
}

/** Erros bloqueantes da distribuição. Vazio = pode aplicar. */
export function errosSelecaoCorridasCfCq(
  quantidadeTotal: number,
  selecoes: SelecaoCorridaCfCq[],
): string[] {
  const erros: string[] = [];
  if (!selecoes.length) return [MSG_SELECIONE_CORRIDAS_CF_CQ];

  const chavesOrigem = new Set<string>();
  let origemDuplicada = false;
  let quantidadeInvalida = false;
  for (const s of selecoes) {
    const chave = chaveOrigemCorridaCfLinha(s.linha);
    if (chavesOrigem.has(chave)) origemDuplicada = true;
    chavesOrigem.add(chave);
    const n = parseQuantidade(s.quantidade);
    if (n == null || n <= 0) quantidadeInvalida = true;
  }
  if (origemDuplicada) erros.push(MSG_ORIGEM_DUPLICADA_CQ);
  if (quantidadeInvalida) erros.push(MSG_QUANTIDADE_CORRIDA_OBRIGATORIA_CQ);

  const { totalDistribuido, saldoRestante } = resumoDistribuicaoCorridasCfCq(quantidadeTotal, selecoes);
  if (!quantidadeInvalida) {
    if (totalDistribuido > quantidadeTotal) erros.push(MSG_SOMA_EXCEDE_TOTAL_CQ);
    else if (saldoRestante !== 0) erros.push(MSG_SOMA_DIFERENTE_TOTAL_CQ);
  }
  return erros;
}

const camposOrigemDocumental = (linha: CorridaCfParaCq): Partial<ItemCertificadoQualidade> => ({
  corrida: linha.corrida,
  lote: linha.lote,
  corrida_snapshot: linha.corrida,
  lote_snapshot: linha.lote,
  certificado_fornecedor_origem_id: linha.certificado_fornecedor_id,
  item_certificado_fornecedor_origem_id: linha.item_certificado_fornecedor_id,
  fornecedor_nome_snapshot: linha.fornecedor_nome,
  nf_entrada_snapshot: linha.numero_nf_entrada,
  numero_certificado_fornecedor_item_snapshot: linha.numero_certificado_fornecedor,
  codigo_item_fornecedor_snapshot: linha.codigo_produto,
  descricao_item_fornecedor_snapshot: linha.descricao_material,
  origem_rastreabilidade_tipo: 'certificado_fornecedor',
});

const normalizarParteOrigem = (value: unknown) =>
  String(value ?? '').replace(/\s+/g, '').toUpperCase();

export function chaveOrigemCorridaCfLinha(linha: CorridaCfParaCq): string {
  return [
    'certificado_fornecedor',
    linha.item_certificado_fornecedor_id,
    normalizarParteOrigem(linha.corrida),
    normalizarParteOrigem(linha.lote),
  ].join(':');
}

export function chaveOrigemCorridaCfItem(item: ItemCertificadoQualidade): string | null {
  if (!item.item_certificado_fornecedor_origem_id) return null;
  const corrida = item.corrida || item.corrida_snapshot || '';
  const lote = item.lote || item.lote_snapshot || '';
  if (!chaveCorridaLoteNormalizada(corrida, lote)) return null;
  return [
    'certificado_fornecedor',
    item.item_certificado_fornecedor_origem_id,
    normalizarParteOrigem(corrida),
    normalizarParteOrigem(lote),
  ].join(':');
}

export function modoDadosTecnicosItemCq(
  item: ItemCertificadoQualidade,
): ModoDadosTecnicosCorridaCq {
  return statusTecnicoNormalizado(item) === ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES
    ? 'proprios'
    : 'herdados';
}

export function selecoesExistentesCorridasCfCq(
  linhas: CorridaCfParaCq[],
  itens: ItemCertificadoQualidade[],
): SelecaoCorridaCfCq[] {
  const itensPorOrigem = new Map(
    itens
      .map((item) => [chaveOrigemCorridaCfItem(item), item] as const)
      .filter(([chave]) => Boolean(chave)),
  );
  return linhas.flatMap((linha) => {
    const item = itensPorOrigem.get(chaveOrigemCorridaCfLinha(linha));
    if (!item) return [];
    return [{
      linha,
      quantidade: String(item.quantidade ?? ''),
      dadosTecnicos: modoDadosTecnicosItemCq(item),
    }];
  });
}

export function quantidadeTotalDistribuicaoCorridasCfCq(
  linhas: CorridaCfParaCq[],
  itens: ItemCertificadoQualidade[],
  itemAtual: ItemCertificadoQualidade,
): number {
  const chaves = new Set(linhas.map(chaveOrigemCorridaCfLinha));
  const grupo = itens.filter((item) => {
    const chave = chaveOrigemCorridaCfItem(item);
    return chave != null && chaves.has(chave);
  });
  if (!grupo.length) return Number(itemAtual.quantidade) || 0;
  return Math.round(
    grupo.reduce((total, item) => total + (Number(item.quantidade) || 0), 0) * 1000,
  ) / 1000;
}

export function itemCqTemDadosTecnicos(item: ItemCertificadoQualidade): boolean {
  const temJson = (data: Record<string, unknown> | undefined) =>
    Object.values(data || {}).some((value) => String(value ?? '').trim() !== '');
  return Boolean(
    String(item.norma || '').trim()
    || temJson(item.composicao_json)
    || temJson(item.ensaio_tracao_json)
    || temJson(item.ensaio_impacto_json),
  );
}

export function aplicacaoSubstituiTecnicosDoItemAtual(
  itemAtual: ItemCertificadoQualidade,
  selecoes: SelecaoCorridaCfCq[],
): boolean {
  if (!itemCqTemDadosTecnicos(itemAtual) || !selecoes.length) return false;
  const chaveAtual = chaveOrigemCorridaCfItem(itemAtual);
  const selecaoAtual = selecoes.find(
    (selecao) => chaveAtual === chaveOrigemCorridaCfLinha(selecao.linha),
  );
  if (!selecaoAtual) return true;
  const mesmoModo = modoDadosTecnicosItemCq(itemAtual) === selecaoAtual.dadosTecnicos;
  return !mesmoModo || !statusTecnicoClassificado(itemAtual);
}

const dadosTecnicosHerdados = (
  linha: CorridaCfParaCq,
): Partial<ItemCertificadoQualidade> => {
  const dt = linha.dados_tecnicos;
  return {
    norma: dt.norma,
    ncm: dt.ncm || undefined,
    composicao_json: { ...(dt.composicao_json || {}) },
    ensaio_tracao_json: { ...(dt.ensaio_tracao_json || {}) },
    ensaio_impacto_json: { ...(dt.ensaio_impacto_json || {}) },
    origem_status_tecnico: ORIGEM_STATUS_TECNICO_HERDADO_CF,
    origem_observacoes: linha.origem_tecnica_label,
  };
};

const dadosTecnicosManuaisVazios = (): Partial<ItemCertificadoQualidade> => ({
  norma: '',
  composicao_json: {},
  ensaio_tracao_json: {},
  ensaio_impacto_json: {},
  origem_status_tecnico: ORIGEM_STATUS_TECNICO_PROPRIOS_PENDENTES,
  origem_observacoes: MSG_DADOS_PROPRIOS_MANUAIS_CQ,
});

const baseItemIrmao = (
  itemOriginal: ItemCertificadoQualidade,
): ItemCertificadoQualidade => ({
  ordem: itemOriginal.ordem || 1,
  id: undefined,
  produto: itemOriginal.produto,
  codigo_produto: itemOriginal.codigo_produto,
  descricao_material: itemOriginal.descricao_material,
  unidade: itemOriginal.unidade,
  ncm: itemOriginal.ncm,
  norma: '',
  tipo_dados_tecnicos: itemOriginal.tipo_dados_tecnicos || 'PADRAO_ITEM',
  produto_snapshot: itemOriginal.produto_snapshot,
  produto_codigo: itemOriginal.produto_codigo,
  produto_descricao: itemOriginal.produto_descricao,
  produto_ncm_efetivo: itemOriginal.produto_ncm_efetivo,
  status_vinculo_produto: itemOriginal.status_vinculo_produto,
  quantidade: 0,
  observacoes_item: itemOriginal.observacoes_item || '',
  composicao_json: {},
  ensaio_tracao_json: {},
  ensaio_impacto_json: {},
  componentes: [],
  incluir_no_certificado: itemOriginal.incluir_no_certificado !== false,
  motivo_nao_inclusao: itemOriginal.motivo_nao_inclusao || '',
  observacao_nao_inclusao: itemOriginal.observacao_nao_inclusao || '',
  corrida: '',
  lote: '',
});

/**
 * Aplica a distribuição somente no array local do editor.
 *
 * Idempotência: itens existentes são encontrados pela chave documental estável.
 * Reaplicar atualiza a quantidade/origem correspondente, preservando técnicos já
 * editados quando o modo (herdado/manual) não mudou. Itens fora das origens do
 * endpoint são mantidos intactos.
 */
export function aplicarDistribuicaoCorridasCfCq(
  itens: ItemCertificadoQualidade[],
  itemAtualIdx: number,
  linhas: CorridaCfParaCq[],
  selecoes: SelecaoCorridaCfCq[],
): ItemCertificadoQualidade[] {
  const itemAtual = itens[itemAtualIdx];
  const chavesDoGrupo = new Set(linhas.map(chaveOrigemCorridaCfLinha));
  const existentesPorChave = new Map<string, ItemCertificadoQualidade>();
  itens.forEach((item) => {
    const chave = chaveOrigemCorridaCfItem(item);
    if (chave && chavesDoGrupo.has(chave) && !existentesPorChave.has(chave)) {
      existentesPorChave.set(chave, item);
    }
  });

  let itemAtualReutilizado = false;
  const itensDistribuidos = selecoes.map((selecao) => {
    const chave = chaveOrigemCorridaCfLinha(selecao.linha);
    const existente = existentesPorChave.get(chave);
    const base = existente || (!itemAtualReutilizado ? itemAtual : baseItemIrmao(itemAtual));
    if (base === itemAtual) itemAtualReutilizado = true;

    const modoAnteriorClassificado = existente && statusTecnicoClassificado(existente);
    const modoAnterior = modoAnteriorClassificado && existente
      ? modoDadosTecnicosItemCq(existente)
      : null;
    let tecnicos: Partial<ItemCertificadoQualidade>;
    if (existente && modoAnterior === selecao.dadosTecnicos) {
      tecnicos = {};
    } else if (selecao.dadosTecnicos === 'herdados') {
      tecnicos = dadosTecnicosHerdados(selecao.linha);
    } else {
      tecnicos = dadosTecnicosManuaisVazios();
    }

    return {
      ...base,
      quantidade: parseQuantidade(selecao.quantidade) ?? 0,
      ...camposOrigemDocumental(selecao.linha),
      ...tecnicos,
    };
  });

  const indicesGrupo = itens
    .map((item, idx) => {
      const chave = chaveOrigemCorridaCfItem(item);
      return idx === itemAtualIdx || (chave != null && chavesDoGrupo.has(chave)) ? idx : -1;
    })
    .filter((idx) => idx >= 0);
  const inserirEm = Math.min(...indicesGrupo);
  const indicesGrupoSet = new Set(indicesGrupo);
  const antes = itens.slice(0, inserirEm).filter((_item, idx) => !indicesGrupoSet.has(idx));
  const depois = itens.slice(inserirEm).filter(
    (_item, offset) => !indicesGrupoSet.has(inserirEm + offset),
  );
  return [...antes, ...itensDistribuidos, ...depois]
    .map((item, idx) => ({ ...item, ordem: idx + 1 }));
}
