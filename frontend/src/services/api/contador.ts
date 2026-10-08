import api from './config';

export type ContadorExportarXmlsParams = {
  inicio: string;
  fim: string;
  tipo: 'nfe_saida' | 'nfe_entrada' | 'cte' | 'todos';
};

async function parseBlobError(blob: Blob, fallback: string): Promise<string> {
  const head = await blob.slice(0, 512).text();
  if (head.trimStart().startsWith('{')) {
    try {
      const j = JSON.parse(await blob.text()) as { detail?: string };
      if (typeof j.detail === 'string' && j.detail.trim()) return j.detail.trim();
    } catch {
      /* resposta não-JSON */
    }
  }
  return fallback;
}

export const contadorService = {
  exportarXmls: async (params: ContadorExportarXmlsParams): Promise<Blob> => {
    try {
      const response = await api.get<Blob>('contador/exportar-xmls/', {
        params,
        responseType: 'blob',
        headers: { Accept: '*/*' },
      });
      return response.data;
    } catch (err: unknown) {
      const ax = err as { response?: { data?: Blob; status?: number } };
      const blob = ax.response?.data;
      if (blob instanceof Blob && ax.response?.status === 400) {
        const detail = await parseBlobError(blob, 'Nenhum XML encontrado para o período e tipo informados.');
        throw new Error(detail);
      }
      throw err;
    }
  },
};
