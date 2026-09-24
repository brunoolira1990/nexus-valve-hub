import api from '@/services/api/config';

export type ParcelaNFe = {
  numero: string;
  vencimento: string;
  valor: string;
};

export async function listarParcelasSugeridas(nfeId: number): Promise<{
  parcelas: ParcelaNFe[];
  valor_total: string;
}> {
  const { data } = await api.get<{ parcelas: any[]; valor_total: number }>(
    `/api/nf-saidas/${nfeId}/parcelas/sugeridas/`,
  );
  return {
    parcelas: data.parcelas.map((p: any) => ({
      numero: String(p.numero_parcela).padStart(3, '0'),
      vencimento: p.vencimento,
      valor: p.valor,
    })),
    valor_total: String(data.valor_total),
  };
}

export async function salvarParcelas(nfeId: number, parcelas: ParcelaNFe[]): Promise<void> {
  await api.patch(`/api/nf-saidas/${nfeId}/parcelas/`, { parcelas });
}
