import { buildDueDates, formatDataIsoParaBr, parsePaymentCondition } from '@/lib/paymentTerms';

export function parsePrazosPagamento(text: string): number[] {
  return parsePaymentCondition(text);
}

export function calcularVencimentos(dataBaseIso: string, prazos: number[]): string[] {
  return buildDueDates(dataBaseIso, prazos);
}

export function formatarResumoParcelas(prazos: number[]): string {
  if (!prazos.length) return 'À vista ou sem prazos definidos';
  if (prazos.length === 1) return `1 parcela: ${prazos[0]} dias`;
  const meio = prazos.slice(0, -1).join(', ');
  return `${prazos.length} parcelas: ${meio} e ${prazos[prazos.length - 1]} dias`;
}

export type VencimentoPrevistoLinha = {
  dias: number;
  dataIso: string;
  dataBr: string;
};

export type CondicaoPagamentoPreview = {
  prazos: number[] | null;
  erro: string | null;
  resumo: string;
  vencimentos: VencimentoPrevistoLinha[];
};

export function previewCondicaoPagamento(condicao: string, dataBaseIso: string): CondicaoPagamentoPreview {
  try {
    const prazos = parsePrazosPagamento(condicao);
    const datas = calcularVencimentos(dataBaseIso, prazos);
    return {
      prazos,
      erro: null,
      resumo: formatarResumoParcelas(prazos),
      vencimentos: prazos.map((dias, i) => ({
        dias,
        dataIso: datas[i] ?? '',
        dataBr: formatDataIsoParaBr(datas[i] ?? ''),
      })),
    };
  } catch (e) {
    return {
      prazos: null,
      erro: e instanceof Error ? e.message : 'Condição inválida',
      resumo: '',
      vencimentos: [],
    };
  }
}
