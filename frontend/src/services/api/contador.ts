import api from './config';

export type ContadorExportarXmlsParams = {
  inicio: string;
  fim: string;
  tipo: 'nfe_saida' | 'nfe_entrada' | 'cte' | 'todos';
};

export const contadorService = {
  exportarXmls: async (params: ContadorExportarXmlsParams): Promise<Blob> => {
    const response = await api.get<Blob>('contador/exportar-xmls/', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },
};
