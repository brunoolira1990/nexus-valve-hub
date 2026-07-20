/** Filtros da listagem de NF-e Saída enviados à API `/api/nf-saidas/`. */

export const NFE_SAIDA_FILTRO_A_PRAZO_SEM_CR = {
  key: 'a_prazo_sem_contas_receber',
  label: 'Contas a receber',
  optionValue: 'true',
  optionLabel: 'Autorizadas a prazo sem Contas a Receber',
} as const;

/** Monta params de listagem apenas com o filtro ativo (omitido quando vazio). */
export function paramsFiltroAPrazoSemContasReceber(
  valor: string | undefined | null,
): Record<string, string> {
  const v = (valor || '').trim();
  if (!v) return {};
  return { [NFE_SAIDA_FILTRO_A_PRAZO_SEM_CR.key]: v };
}
