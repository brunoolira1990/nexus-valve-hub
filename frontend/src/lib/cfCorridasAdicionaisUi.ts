/**
 * Tarefa A1 — Corridas adicionais com os mesmos dados técnicos no Certificado de Fornecedor.
 *
 * Regra de quantidades (sem campo novo / sem migration):
 * - `quantidade` do item = total recebido;
 * - quantidade da corrida principal é DERIVADA: total − soma das quantidades das adicionais;
 * - soma das adicionais menor que o total é a distribuição NORMAL (a principal recebe o saldo);
 * - soma igual ao total deixa a principal sem quantidade → bloqueia;
 * - soma maior que o total → bloqueia;
 * - linhas antigas sem quantidade seguem aceitas (aviso de distribuição incompleta, sem backfill).
 */
import type { ItemCertificadoFornecedorCorrida, ItemCertificadoFornecedorEntrada } from '@/types';

export const TITULO_CORRIDAS_ADICIONAIS_CF = 'Corridas adicionais com os mesmos dados técnicos';

export const TEXTO_EXPLICATIVO_CORRIDAS_ADICIONAIS_CF =
  'Use esta seção somente quando as corridas compartilham composição química, propriedades mecânicas, '
  + 'ensaios, norma e demais dados técnicos do item principal. Para corridas com dados diferentes, '
  + 'será necessário criar um item independente.';

export const AVISO_DADOS_HERDADOS_CORRIDA_CF = 'Dados técnicos herdados do item principal';

export const MSG_CORRIDA_COMPARTILHA_DADOS_CF = 'Esta corrida compartilha os dados técnicos do item principal.';
export const MSG_DISTRIBUICAO_INCOMPLETA_CF = 'A distribuição das quantidades por corrida está incompleta.';
export const MSG_SOMA_EXCEDE_QUANTIDADE_ITEM_CF = 'A soma das quantidades das corridas excede a quantidade do item.';
export const MSG_PRINCIPAL_SEM_QUANTIDADE_CF =
  'A distribuição deixa a corrida principal sem quantidade. '
  + 'Ajuste as quantidades ou represente a origem em outro item do certificado.';
export const MSG_CORRIDA_LOTE_DUPLICADA_CF = 'Esta corrida/lote já está vinculada a este item.';
export const MSG_QUANTIDADE_OBRIGATORIA_NOVA_CORRIDA_CF =
  'Informe quantidade maior que zero para a nova corrida adicional.';
export const MSG_CORRIDA_OBRIGATORIA_LINHA_ADICIONAL_CF =
  'Informe a corrida/lote da linha adicional ou remova a linha.';
export const MSG_MULTIPLOS_CERTIFICADOS_COMPATIVEIS_CF =
  'Há mais de um Certificado de Fornecedor compatível; selecione a origem.';

/** Chave normalizada de duplicidade: caixa alta e sem espaços (diferenças triviais não contam). */
export function chaveCorridaLoteNormalizada(corrida?: string | null, lote?: string | null): string {
  const c = (corrida || '').toUpperCase().replace(/\s+/g, '');
  const l = (lote || '').toUpperCase().replace(/\s+/g, '');
  if (!c && !l) return '';
  return `${c}\u001f${l}`;
}

export type ResumoQuantidadesCorridasItemCf = {
  quantidadeItem: number | null;
  somaAdicionais: number;
  /** total − soma das adicionais; null quando não é possível derivar. */
  principalDerivada: number | null;
  temAdicionalSemQuantidade: boolean;
  excedeQuantidadeItem: boolean;
  /** Soma das adicionais igual ao total com a principal preenchida: principal ficaria com zero. */
  principalSemQuantidade: boolean;
  /** Só para lacuna real (linha sem quantidade / total indeterminável) — soma menor que o total é normal. */
  distribuicaoIncompleta: boolean;
};

type ItemComCorridas = Pick<ItemCertificadoFornecedorEntrada, 'quantidade' | 'corrida' | 'lote' | 'corridas_adicionais'>;

function linhaAdicionalPreenchida(ca: ItemCertificadoFornecedorCorrida): boolean {
  return Boolean((ca.corrida || '').trim() || (ca.lote || '').trim());
}

export function resumoQuantidadesCorridasItemCf(item: ItemComCorridas): ResumoQuantidadesCorridasItemCf {
  const adicionais = (item.corridas_adicionais || []).filter(linhaAdicionalPreenchida);
  const quantidadeItem = item.quantidade == null || Number.isNaN(Number(item.quantidade))
    ? null
    : Number(item.quantidade);
  let somaAdicionais = 0;
  let temAdicionalSemQuantidade = false;
  for (const ca of adicionais) {
    if (ca.quantidade == null || Number.isNaN(Number(ca.quantidade))) {
      temAdicionalSemQuantidade = true;
      continue;
    }
    somaAdicionais += Number(ca.quantidade);
  }
  const podeDerivar = quantidadeItem != null && quantidadeItem > 0 && !temAdicionalSemQuantidade;
  const principalDerivada = podeDerivar ? quantidadeItem - somaAdicionais : null;
  const excedeQuantidadeItem = quantidadeItem != null && quantidadeItem > 0 && somaAdicionais > quantidadeItem;
  const principalPreenchida = Boolean(chaveCorridaLoteNormalizada(item.corrida, item.lote));
  const principalSemQuantidade = principalPreenchida
    && quantidadeItem != null
    && quantidadeItem > 0
    && somaAdicionais > 0
    && somaAdicionais === quantidadeItem;
  const distribuicaoIncompleta = adicionais.length > 0
    && (temAdicionalSemQuantidade || quantidadeItem == null || quantidadeItem <= 0);
  return {
    quantidadeItem,
    somaAdicionais,
    principalDerivada,
    temAdicionalSemQuantidade,
    excedeQuantidadeItem,
    principalSemQuantidade,
    distribuicaoIncompleta,
  };
}

/**
 * Erros que impedem salvar (deduplicados). Linhas antigas (com `id`) sem quantidade
 * não bloqueiam: compatibilidade com certificados históricos, sem backfill.
 */
export function errosCorridasAdicionaisItemCf(item: ItemComCorridas): string[] {
  const erros: string[] = [];
  const adicionais = item.corridas_adicionais || [];
  if (!adicionais.length) return erros;

  const chaves = new Set<string>();
  const chavePrincipal = chaveCorridaLoteNormalizada(item.corrida, item.lote);
  if (chavePrincipal) chaves.add(chavePrincipal);

  let duplicada = false;
  let linhaVazia = false;
  let quantidadeInvalida = false;
  for (const ca of adicionais) {
    if (!linhaAdicionalPreenchida(ca)) {
      linhaVazia = true;
      continue;
    }
    const chave = chaveCorridaLoteNormalizada(ca.corrida, ca.lote);
    if (chave) {
      if (chaves.has(chave)) duplicada = true;
      chaves.add(chave);
    }
    const linhaNova = ca.id == null;
    const quantidadeAusente = ca.quantidade == null || Number.isNaN(Number(ca.quantidade));
    if (quantidadeAusente) {
      if (linhaNova) quantidadeInvalida = true;
    } else if (Number(ca.quantidade) <= 0) {
      quantidadeInvalida = true;
    }
  }

  if (duplicada) erros.push(MSG_CORRIDA_LOTE_DUPLICADA_CF);
  if (linhaVazia) erros.push(MSG_CORRIDA_OBRIGATORIA_LINHA_ADICIONAL_CF);
  if (quantidadeInvalida) erros.push(MSG_QUANTIDADE_OBRIGATORIA_NOVA_CORRIDA_CF);
  const resumo = resumoQuantidadesCorridasItemCf(item);
  if (resumo.excedeQuantidadeItem) {
    erros.push(MSG_SOMA_EXCEDE_QUANTIDADE_ITEM_CF);
  } else if (resumo.principalSemQuantidade) {
    erros.push(MSG_PRINCIPAL_SEM_QUANTIDADE_CF);
  }
  return erros;
}

/** Avisos não bloqueantes — só lacuna real (linha histórica sem quantidade / total indeterminável). */
export function avisosCorridasAdicionaisItemCf(item: ItemComCorridas): string[] {
  const resumo = resumoQuantidadesCorridasItemCf(item);
  if (resumo.excedeQuantidadeItem || resumo.principalSemQuantidade) return [];
  if (resumo.distribuicaoIncompleta) return [MSG_DISTRIBUICAO_INCOMPLETA_CF];
  return [];
}
