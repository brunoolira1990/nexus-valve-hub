import api from './config';

export type NotaChatter = {
  id: number;
  entity_type: string;
  entity_id: number;
  texto: string;
  autor: number | null;
  autor_nome: string | null;
  criado_em: string;
  atualizado_em: string;
};

export type NotaChatterListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: NotaChatter[];
};

export const chatterNotasService = {
  listar: async (
    entityType: string,
    entityId: number,
    params?: { page?: number; page_size?: number },
  ) =>
    (
      await api.get<NotaChatterListResponse>('chatter/notas/', {
        params: { entity_type: entityType, entity_id: entityId, ...params },
      })
    ).data,

  criar: async (input: { entity_type: string; entity_id: number; texto: string }) =>
    (await api.post<NotaChatter>('chatter/notas/', input)).data,

  atualizar: async (id: number, texto: string) =>
    (await api.patch<NotaChatter>(`chatter/notas/${id}/`, { texto })).data,

  excluir: async (id: number) => (await api.delete(`chatter/notas/${id}/`)).data,
};
