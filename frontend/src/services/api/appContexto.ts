import api from './config';

export type AppContextoEmpresa = {
  id: number;
  nome_exibicao: string;
  nome_curto?: string;
  razao_social: string;
  cnpj: string;
  ambiente: string;
};

export type AppContextoUsuario = {
  id: number;
  nome: string;
  nome_exibicao: string;
  nome_curto?: string;
  email: string;
  email_tecnico?: boolean;
  username: string;
  first_name?: string;
  last_name?: string;
  perfil: string;
  perfil_label: string;
  is_admin: boolean;
  is_staff?: boolean;
  is_superuser?: boolean;
  is_active?: boolean;
  colaborador_id?: number | null;
  colaborador_nome?: string;
};

export type AppContextoColaborador = {
  id: number;
  nome: string;
  codigo: string;
  email: string;
  telefone?: string;
  cargo?: string;
  departamento?: string;
  ativo?: boolean;
  funcoes_internas: string[];
};

export type AppContexto = {
  empresa: AppContextoEmpresa | null;
  usuario: AppContextoUsuario;
  colaborador: AppContextoColaborador | null;
  ambiente: string;
  ambiente_label: string;
};

export type MinhaConta = AppContexto & {
  avisos: string[];
};

export type MinhaContaUpdatePayload = {
  email?: string;
  telefone?: string;
};

export type BuscaGlobalItem = {
  tipo: string;
  tipo_label: string;
  grupo: string;
  titulo: string;
  subtitulo: string;
  url: string;
};

export type BuscaGlobalResponse = {
  query: string;
  resultados: BuscaGlobalItem[];
  mensagem?: string;
};

export const appContextoService = {
  getContexto: async () => (await api.get<AppContexto>('app/contexto/')).data,
  getMinhaConta: async () => (await api.get<MinhaConta>('minha-conta/')).data,
  patchMinhaConta: async (payload: MinhaContaUpdatePayload) =>
    (await api.patch<MinhaConta & { mensagem?: string }>('minha-conta/', payload)).data,
  buscaGlobal: async (q: string) =>
    (await api.get<BuscaGlobalResponse>('busca-global/', { params: { q } })).data,
};
