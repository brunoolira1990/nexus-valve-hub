import type {
  AtualizarImpostosAlteracao,
  AtualizarImpostosItemPreview,
  AtualizarImpostosPreviewResponse,
  TextoFiscalAlteracao,
  TextosFiscaisPreview,
} from '@/services/api/fiscal';
import { mensagemPreviewSemRegra } from '@/lib/enderecoFiscal';

const STATUS_NFE_BLOQUEIA_ATUALIZAR_IMPOSTOS = new Set([
  'AUTORIZADA_INTERNA',
  'AUTORIZADA',
  'EMITIDA',
  'EMITIDO',
  'CANCELADA_INTERNA',
  'CANCELADA',
  'CANCELADO',
]);

const CAMPOS_FISCAL_ATUAL = new Set([
  'cfop',
  'cfop_venda',
  'cfop_saida',
  'cfop_st',
  'cst_icms',
  'csosn',
  'modalidade_bc_icms',
  'base_icms',
  'aliquota_icms',
  'valor_icms',
  'reducao_bc_icms',
  'icms_st_aplicavel',
  'aliquota_icms_st',
  'base_icms_st',
  'valor_icms_st',
  'fcp_aplicavel',
  'base_fcp',
  'aliquota_fcp',
  'valor_fcp',
  'cst_ipi',
  'base_ipi',
  'aliquota_ipi',
  'valor_ipi',
  'cst_pis',
  'base_pis',
  'aliquota_pis',
  'valor_pis',
  'cst_cofins',
  'base_cofins',
  'aliquota_cofins',
  'valor_cofins',
  'deduzir_icms_base_pis',
  'deduzir_icms_base_cofins',
  'icms_saida_percentual',
  'ipi_saida_percentual',
  'pis_saida_percentual',
  'cofins_saida_percentual',
]);

const CAMPOS_REFORMA = new Set([
  'reforma_tributaria',
  'cst_ibs_cbs',
  'classificacao_tributaria',
  'base_cbs',
  'aliquota_cbs',
  'valor_cbs',
  'reducao_cbs',
  'diferimento_cbs',
  'credito_presumido_cbs',
  'base_ibs',
  'aliquota_ibs_estadual',
  'valor_ibs_estadual',
  'valor_ibs_uf',
  'aliquota_ibs_municipal',
  'valor_ibs_municipal',
  'reducao_ibs',
  'diferimento_ibs',
  'credito_presumido_ibs',
  'observacoes_reforma',
]);

const CAMPOS_METADADOS = new Set([
  'regra_fiscal_saida_id',
  'regra_fiscal_saida_nome',
  'regra_fiscal_legada_id',
  'cenario_fiscal_saida_id',
  'cenario_fiscal_saida_nome',
  'fonte',
  'atualizado_por_acao',
  'atualizado_em',
  'origem_regra_fiscal_saida',
  'recomendacoes_nfe',
]);

export type GrupoAlteracaoImposto = 'fiscal_atual' | 'reforma_tributaria' | 'metadados' | 'outros';

export const ORDEM_GRUPOS_ALTERACAO: GrupoAlteracaoImposto[] = [
  'fiscal_atual',
  'reforma_tributaria',
  'outros',
  'metadados',
];

export function grupoAlteracaoImposto(campo: string): GrupoAlteracaoImposto {
  const c = (campo || '').trim().toLowerCase();
  if (CAMPOS_METADADOS.has(c)) return 'metadados';
  if (CAMPOS_REFORMA.has(c)) return 'reforma_tributaria';
  if (CAMPOS_FISCAL_ATUAL.has(c)) return 'fiscal_atual';
  if (c.includes('ibs') || c.includes('cbs') || c.includes('reforma')) return 'reforma_tributaria';
  if (c.includes('icms') || c.includes('ipi') || c.includes('pis') || c.includes('cofins') || c.includes('cfop') || c.includes('fcp')) {
    return 'fiscal_atual';
  }
  return 'outros';
}

export function labelGrupoAlteracao(grupo: GrupoAlteracaoImposto): string {
  switch (grupo) {
    case 'fiscal_atual':
      return 'Fiscal atual';
    case 'reforma_tributaria':
      return 'Reforma Tributária';
    case 'metadados':
      return 'Metadados da regra';
    default:
      return 'Outros';
  }
}

export type AlteracaoAgrupada = {
  campo: string;
  label: string;
  antes: string;
  depois: string;
};

export type ItemAlteracoesAgrupadas = {
  itemId: number;
  produtoNome: string;
  ncm: string;
  regraEncontrada: boolean;
  regraNome: string;
  grupos: Partial<Record<GrupoAlteracaoImposto, AlteracaoAgrupada[]>>;
  alertas: string[];
};

export function agruparAlteracoesPorItem(itens: AtualizarImpostosItemPreview[]): ItemAlteracoesAgrupadas[] {
  return itens
    .filter((it) => it.regra_encontrada && (it.alteracoes?.length ?? 0) > 0)
    .map((it) => {
      const grupos: Partial<Record<GrupoAlteracaoImposto, AlteracaoAgrupada[]>> = {};
      for (const alt of it.alteracoes ?? []) {
        const grupo = grupoAlteracaoImposto(alt.campo);
        if (!grupos[grupo]) grupos[grupo] = [];
        grupos[grupo]!.push({
          campo: alt.campo,
          label: alt.label,
          antes: alt.antes,
          depois: alt.depois,
        });
      }
      return {
        itemId: it.item_id,
        produtoNome: it.produto_nome,
        ncm: it.ncm,
        regraEncontrada: it.regra_encontrada,
        regraNome: it.regra_fiscal_saida_nome || '',
        grupos,
        alertas: it.alertas ?? [],
      };
    });
}

export function itensSemRegraDoPreview(itens: AtualizarImpostosItemPreview[]) {
  return itens.filter((it) => !it.regra_encontrada);
}

export function totalAlteracoesImpostosItens(preview: AtualizarImpostosPreviewResponse | null): number {
  if (!preview?.itens) return 0;
  return preview.itens.reduce((acc, it) => acc + (it.alteracoes?.length ?? 0), 0);
}

export function totalTextosFiscaisSugeridos(preview: AtualizarImpostosPreviewResponse | null): number {
  return preview?.resumo?.textos_fiscais_sugeridos ?? preview?.textos_fiscais?.alteracoes?.length ?? 0;
}

export function temAlteracaoAplicavel(preview: AtualizarImpostosPreviewResponse | null): boolean {
  if (!preview?.pode_aplicar || preview.bloqueado) return false;
  const impostos = preview.resumo?.itens_com_alteracao ?? 0;
  const textos = totalTextosFiscaisSugeridos(preview);
  const rec = preview.resumo?.recomendacoes_sugeridas ?? 0;
  return impostos > 0 || textos > 0 || rec > 0;
}

/** @deprecated use totalAlteracoesImpostosItens */
export function totalAlteracoesPreview(preview: AtualizarImpostosPreviewResponse | null): number {
  return totalAlteracoesImpostosItens(preview);
}

export function itensSemRegraPreview(preview: AtualizarImpostosPreviewResponse | null): number {
  return preview?.resumo?.itens_sem_regra ?? 0;
}

export function podeExibirBotaoAtualizarImpostos(
  status: string | undefined,
  podeAtualizar: boolean | undefined,
  itensTotal: number,
): boolean {
  const st = (status || '').trim().toUpperCase();
  if (STATUS_NFE_BLOQUEIA_ATUALIZAR_IMPOSTOS.has(st)) return false;
  if (st !== 'RASCUNHO' || itensTotal < 1) return false;
  if (typeof podeAtualizar === 'boolean') return podeAtualizar;
  return true;
}

export function tooltipAtualizarImpostos(
  status: string | undefined,
  podeAtualizar: boolean | undefined,
  itensTotal: number,
): string {
  if (podeExibirBotaoAtualizarImpostos(status, podeAtualizar, itensTotal)) return '';
  const st = (status || '').trim().toUpperCase();
  if (itensTotal < 1) return 'NF-e sem itens para atualizar impostos.';
  if (st !== 'RASCUNHO') return 'Disponível apenas para NF-e em rascunho.';
  return 'Atualização de impostos indisponível neste status.';
}

/** @deprecated Prefer agruparAlteracoesPorItem */
export type LinhaComparativoImpostos = {
  itemId: number;
  produtoNome: string;
  campo: string;
  label: string;
  antes: string;
  depois: string;
  temReforma: boolean;
};

export function linhasComparativoImpostos(itens: AtualizarImpostosItemPreview[]): LinhaComparativoImpostos[] {
  const rows: LinhaComparativoImpostos[] = [];
  for (const it of itens) {
    for (const alt of it.alteracoes ?? []) {
      const grupo = grupoAlteracaoImposto(alt.campo);
      rows.push({
        itemId: it.item_id,
        produtoNome: it.produto_nome,
        campo: alt.campo,
        label: alt.label,
        antes: alt.antes,
        depois: alt.depois,
        temReforma: grupo === 'reforma_tributaria',
      });
    }
  }
  return rows;
}

export function mensagemPosPreview(preview: AtualizarImpostosPreviewResponse): string {
  if (preview.bloqueado) return preview.mensagem || 'Atualização bloqueada.';
  if (!preview.pode_aplicar) {
    return mensagemConfirmarDesabilitado(preview);
  }
  if (totalTextosFiscaisSugeridos(preview) > 0 && (preview.resumo?.itens_com_alteracao ?? 0) === 0) {
    return 'Há textos fiscais/recomendações para aplicar.';
  }
  return '';
}

export function mensagemConfirmarDesabilitado(preview: AtualizarImpostosPreviewResponse | null): string {
  if (!preview) return 'Carregando prévia…';
  if (preview.bloqueado) return preview.mensagem || 'Atualização bloqueada.';
  if (!preview.pode_aplicar) {
    return mensagemPreviewSemRegra(preview);
  }
  return '';
}

export function podeConfirmarAplicarImpostos(preview: AtualizarImpostosPreviewResponse | null): boolean {
  return temAlteracaoAplicavel(preview);
}

export function isAlteracaoTextoFiscal(campo: string): boolean {
  return ['informacoes_adicionais', 'observacoes_nfe', 'informacoes_fisco'].includes(campo);
}

/** Textos que não devem aparecer no modal focado (abas da conferência). */
export const ABAS_CONFERENCIA_PROIBIDAS_NO_MODAL = [
  'Resumo',
  'Itens',
  'Fiscal atual',
  'Reforma',
  'Transporte',
  'Observações',
  'Validação',
  'Histórico',
] as const;
