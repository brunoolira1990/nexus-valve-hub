import api from './config';

export type AnexoChatter = {
  id: number;
  nota: number;
  nome_original: string;
  tamanho_bytes: number;
  criado_em: string;
  /** Caminho raiz-relativo servido por /media (proxy do Vite em dev, Caddy em prod). */
  arquivo_url: string;
};

export type NotaChatter = {
  id: number;
  entity_type: string;
  entity_id: number;
  texto: string;
  autor: number | null;
  autor_nome: string | null;
  anexos: AnexoChatter[];
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

  uploadAnexo: async (notaId: number, arquivo: File) => {
    const fd = new FormData();
    fd.append('nota', String(notaId));
    fd.append('arquivo', arquivo);
    return (
      await api.post<AnexoChatter>('chatter/anexos/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    ).data;
  },

  excluirAnexo: async (id: number) => {
    await api.delete(`chatter/anexos/${id}/`);
  },
};
