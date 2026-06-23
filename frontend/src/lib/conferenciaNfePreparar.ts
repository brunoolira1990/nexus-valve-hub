import axios, { type AxiosError } from 'axios';
import { apiErrorMessage } from '@/services/api/config';

type PrepararEstoqueErrorBody = {
  detail?: string;
  pendencias?: string[];
  bloqueio_fiscal?: boolean;
  data_entrada_ausente?: boolean;
  migrations_pendentes?: boolean;
};

/** Mensagem de erro ao preparar estoque (inclui pendências e bloqueio fiscal). */
export function prepararEstoqueErrorMessage(err: unknown): string {
  const ax = err as AxiosError<PrepararEstoqueErrorBody>;
  const data = ax.response?.data;
  const pendencias = data?.pendencias;

  if (data?.migrations_pendentes && data?.detail) {
    return data.detail;
  }

  if (data?.data_entrada_ausente) {
    return [
      'Informe e salve a data de entrada da NF-e antes de preparar estoque.',
      ...(pendencias || []),
    ].join('\n');
  }
  if (data?.bloqueio_fiscal) {
    const configEntrada = pendencias?.some((p) =>
      /entrada fiscal|regra fiscal de entrada/i.test(p),
    );
    const linhas = configEntrada
      ? [
          'Cadastre regra fiscal de entrada antes de finalizar esta entrada fiscal.',
          'Cadastre uma regra fiscal de entrada com CFOP, natureza e CST/CSOSN.',
        ]
      : [
          'A conferência possui itens bloqueados por regra fiscal. Revise as regras fiscais de entrada antes de preparar.',
          'Os itens bloqueados aparecem no painel Resumo fiscal (entrada), contador Bloqueado, e na coluna Fiscal de cada linha.',
        ];
    if (pendencias?.length) {
      linhas.push('', ...pendencias);
    }
    return linhas.join('\n');
  }

  if (pendencias?.length) {
    return [data?.detail, ...pendencias].filter(Boolean).join('\n');
  }

  return apiErrorMessage(err);
}
