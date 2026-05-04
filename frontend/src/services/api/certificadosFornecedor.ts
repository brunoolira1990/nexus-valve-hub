import api from './config';
import type {
  CertificadoFornecedorEntrada,
  DadosTecnicosFornecedorResultado,
} from '@/types';

const base = 'certificados-fornecedor/';

export type PreencherPorNFeEntradaPayload = {
  nf_entrada_historica_id?: number;
  nf_entrada_operacional_id?: number;
};

export type PreencherPorNFeEntradaResponse = Partial<CertificadoFornecedorEntrada> & {
  mensagens?: string[];
};

export type BuscarDadosTecnicosFornecedorParams = {
  corrida?: string;
  lote?: string;
  produto?: number;
  codigo_produto?: string;
  descricao?: string;
  norma?: string;
  tipo_dados_tecnicos?: 'PADRAO_ITEM' | 'VALVULA_COMPONENTES';
  fornecedor?: number;
  nf_entrada?: string;
  certificado_fornecedor?: string;
  status?: 'rascunho' | 'registrado' | 'cancelado';
  include_rascunho?: boolean;
};

export const certificadosFornecedorService = {
  getAll: async () => (await api.get<CertificadoFornecedorEntrada[]>(base)).data,
  getById: async (id: number) => (await api.get<CertificadoFornecedorEntrada>(`${base}${id}/`)).data,
  create: async (payload: Omit<CertificadoFornecedorEntrada, 'id' | 'criado_em' | 'atualizado_em'>) =>
    (await api.post<CertificadoFornecedorEntrada>(base, payload)).data,
  update: async (id: number, payload: Partial<CertificadoFornecedorEntrada>) =>
    (await api.patch<CertificadoFornecedorEntrada>(`${base}${id}/`, payload)).data,
  preencherPorNfeEntrada: async (payload: PreencherPorNFeEntradaPayload) =>
    (await api.post<PreencherPorNFeEntradaResponse>(`${base}preencher-por-nfe-entrada/`, payload)).data,
  buscarDadosTecnicos: async (params: BuscarDadosTecnicosFornecedorParams) =>
    (await api.get<DadosTecnicosFornecedorResultado[]>(`${base}buscar-dados-tecnicos/`, { params })).data,
};
