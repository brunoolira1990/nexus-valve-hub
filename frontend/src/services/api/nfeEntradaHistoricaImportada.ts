import api from './config';

const base = 'nf-entradas-historicas-importadas/';

export type NFeEntradaHistoricaList = {
  id: number;
  numero: string;
  serie: string;
  chave_acesso: string;
  dh_emissao: string;
  valor_total_nf: number;
  emit_json?: Record<string, unknown>;
  fornecedor_nome: string;
  fornecedor_cnpj: string;
  fornecedor_id?: number | null;
};

export const nfeEntradaHistoricaImportadaService = {
  list: async () => (await api.get<NFeEntradaHistoricaList[]>(base)).data,
};
