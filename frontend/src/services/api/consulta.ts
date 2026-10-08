import api from './config';

export type ConsultaCepResponse = {
  logradouro: string;
  complemento?: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
};

export type ConsultaCnpjResponse = {
  cnpj?: string;
  razao_social: string;
  nome_fantasia?: string;
  inscricao_estadual?: string;
  inscricao_estadual_disponivel?: boolean;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email?: string;
  codigo_municipio?: string;
  cnae?: string;
  regime_tributario?: string;
  aviso_ie?: string;
  consulta_ie_pendente?: boolean;
  fonte?: string;
};

export type InscricaoEstadualSefazItem = {
  inscricao_estadual: string;
  situacao_ie: string;
  situacao_codigo?: string;
  uf: string;
  cnpj?: string;
  razao_social?: string;
  municipio?: string;
  cnae?: string;
  habilitada?: boolean;
};

export type ConsultaIeResponse = {
  sucesso: boolean;
  cnpj?: string;
  uf?: string;
  inscricao_estadual?: string;
  inscricoes_estaduais?: InscricaoEstadualSefazItem[];
  situacao_ie?: string;
  razao_social?: string;
  municipio?: string;
  cnae?: string;
  fonte?: string;
  ambiente?: string;
  mensagem_usuario?: string;
  erro_codigo?: string;
  detail?: string;
};

/** GET /api/consulta-ie/ — consulta IE na SEFAZ (autenticada). */
export const consultaIe = (params: { cnpj: string; uf: string; empresa_id?: number }) =>
  api.get<ConsultaIeResponse>('consulta-ie/', { params });
export const consultaCep = (cep: string) =>
  api.get<ConsultaCepResponse>(`consulta-cep/${cep}/`);

/** GET /api/consulta-cnpj/<cnpj>/ — `cnpj` pode vir formatado; o backend normaliza. */
export const consultaCnpj = (cnpj: string) =>
  api.get<ConsultaCnpjResponse>(`consulta-cnpj/${cnpj}/`);
