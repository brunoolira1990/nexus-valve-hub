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
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email?: string;
};

/** GET /api/consulta-cep/<cep>/ — `cep` pode vir formatado; o backend normaliza. */
export const consultaCep = (cep: string) =>
  api.get<ConsultaCepResponse>(`consulta-cep/${cep}/`);

/** GET /api/consulta-cnpj/<cnpj>/ — `cnpj` pode vir formatado; o backend normaliza. */
export const consultaCnpj = (cnpj: string) =>
  api.get<ConsultaCnpjResponse>(`consulta-cnpj/${cnpj}/`);
