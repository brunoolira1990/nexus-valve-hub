import api from './config';

export type CertificadoNfeValidacao = {
  valido: boolean;
  titular?: string | null;
  cnpj?: string | null;
  cpf?: string | null;
  razao_social?: string | null;
  validade_inicio?: string | null;
  validade_fim?: string | null;
  vencido?: boolean;
  dias_para_vencimento?: number | null;
  expirado?: boolean;
  expira_em_dias?: number | null;
  mensagens?: string[];
  erro?: string | null;
};

export type NFeSefazStatusConsulta = {
  id: number;
  empresa: number;
  empresa_razao_social: string;
  empresa_cnpj: string;
  uf: string;
  ambiente: string;
  modelo: string;
  ok?: boolean;
  sucesso: boolean;
  c_stat: string;
  cstat?: string;
  x_motivo: string;
  motivo?: string;
  ver_aplic: string;
  servico_operacional: boolean;
  certificado_valido: boolean;
  certificado_cnpj: string;
  certificado_validade_fim: string | null;
  erro_tecnico: string;
  tipo_erro: string;
  raw_response?: string;
  xml_resposta?: string;
  xml_retorno?: string;
  mensagens: string[];
  consultado_em: string;
  resultado?: Record<string, unknown>;
};

export type NFeSefazConsultaResponse = NFeSefazStatusConsulta & {
  ok: boolean;
  cstat: string;
  motivo: string;
  xml_retorno: string;
};

export const nfeSefazService = {
  listarHistorico: async () =>
    (await api.get<NFeSefazStatusConsulta[]>('/nfe-sefaz-status/')).data,

  consultarStatusServico: async (payload: {
    empresa_id: number;
    uf?: string;
    homologacao?: boolean;
  }) =>
    (
      await api.post<NFeSefazConsultaResponse>('/nfe-sefaz-status/consultar/', {
        empresa_id: payload.empresa_id,
        uf: payload.uf ?? 'SP',
        homologacao: payload.homologacao ?? true,
      })
    ).data,

  validarCertificadoEmpresa: async (empresaId: number) =>
    (
      await api.get<CertificadoNfeValidacao>(
        `/empresas/${empresaId}/validar-certificado-nfe/`,
      )
    ).data,
};
