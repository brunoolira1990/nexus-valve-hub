import api from './config';

export type AuditoriaAtor = {
  id: number | null;
  nome: string | null;
};

export type AuditoriaCampoAlteracao =
  | { antes: unknown; depois: unknown; sensivel?: never; alterado?: never }
  | { sensivel: true; alterado: true; antes?: never; depois?: never };

export type RegistroAuditoria = {
  id: number;
  operacao: 'CREATE' | 'UPDATE' | string;
  ator: AuditoriaAtor;
  criado_em: string;
  alteracoes: Record<string, AuditoriaCampoAlteracao>;
};

export type AuditoriaHistoricoResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: RegistroAuditoria[];
};

export const auditoriaService = {
  capacidade: async () =>
    (await api.get<{ pode_visualizar: boolean }>('auditoria/capacidade/')).data,
  historicoObjeto: async (
    appLabel: string,
    modelName: string,
    objectId: number,
    params?: { page?: number; page_size?: number },
  ) =>
    (
      await api.get<AuditoriaHistoricoResponse>(
        `auditoria/objetos/${appLabel}/${modelName}/${objectId}/`,
        { params },
      )
    ).data,
};
