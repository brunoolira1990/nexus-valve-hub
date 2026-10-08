/** Recomendações operacionais NF-e/DANFE (cadastro preparatório). */

export const RECOMENDACOES_NFE_KEYS = [
  'danfe_paisagem',
  'nao_preencher_data_hora_saida',
  'ocultar_destaque_pis_cofins',
  'ocultar_destaque_icms_st_itens',
  'ordenar_itens_por_descricao',
  'exibir_email_destinatario',
  'exibir_cest_informacoes_item',
  'exibir_pedido_compra_item',
  'exibir_chave_dfe_referenciado',
  'emitir_etiqueta_danfe_simplificado',
  'enviar_retencoes_como_desconto',
] as const;

export type RecomendacaoNfeKey = (typeof RECOMENDACOES_NFE_KEYS)[number];

export type RecomendacoesNfeForm = Record<RecomendacaoNfeKey, boolean>;

export const RECOMENDACOES_NFE_OPCOES: { key: RecomendacaoNfeKey; label: string }[] = [
  { key: 'danfe_paisagem', label: 'Emitir DANFE em formato paisagem' },
  { key: 'nao_preencher_data_hora_saida', label: 'Não preencher Data/Hora de Saída' },
  { key: 'ocultar_destaque_pis_cofins', label: 'Não exibir destaque do PIS/COFINS' },
  { key: 'ocultar_destaque_icms_st_itens', label: 'Não exibir destaque do ICMS ST nos itens' },
  { key: 'ordenar_itens_por_descricao', label: 'Ordenar itens por descrição' },
  { key: 'exibir_email_destinatario', label: 'Exibir e-mail do destinatário nas informações adicionais' },
  { key: 'exibir_cest_informacoes_item', label: 'Exibir CEST nas informações adicionais do item' },
  { key: 'exibir_pedido_compra_item', label: 'Exibir número e item do Pedido de Compra' },
  { key: 'exibir_chave_dfe_referenciado', label: 'Exibir chave do DFe referenciado no item' },
  { key: 'emitir_etiqueta_danfe_simplificado', label: 'Emitir etiqueta DANFE / DANFE simplificado' },
  { key: 'enviar_retencoes_como_desconto', label: 'Enviar retenções como desconto' },
];

export const AVISO_RECOMENDACOES_NFE =
  'Estas recomendações serão usadas futuramente na emissão de NF-e/DANFE. Nesta fase, são apenas cadastro.';

export function emptyRecomendacoesNfe(): RecomendacoesNfeForm {
  return Object.fromEntries(RECOMENDACOES_NFE_KEYS.map((k) => [k, false])) as RecomendacoesNfeForm;
}

export function recomendacoesFromApi(raw: Record<string, unknown> | null | undefined): RecomendacoesNfeForm {
  const base = emptyRecomendacoesNfe();
  if (!raw || typeof raw !== 'object') return base;
  for (const key of RECOMENDACOES_NFE_KEYS) {
    if (key in raw) base[key] = Boolean(raw[key]);
  }
  return base;
}

export function recomendacoesToApi(form: RecomendacoesNfeForm): Record<string, boolean> | null {
  const out: Record<string, boolean> = {};
  for (const key of RECOMENDACOES_NFE_KEYS) {
    if (form[key]) out[key] = true;
  }
  return Object.keys(out).length ? out : null;
}

export function contarRecomendacoesAtivas(form: RecomendacoesNfeForm): number {
  return RECOMENDACOES_NFE_KEYS.filter((k) => form[k]).length;
}

export function temRecomendacoesAtivas(form: RecomendacoesNfeForm): boolean {
  return contarRecomendacoesAtivas(form) > 0;
}
