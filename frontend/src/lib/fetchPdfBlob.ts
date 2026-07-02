import type { AxiosResponse } from 'axios';

import api from '@/services/api/config';
import { parseContentDispositionFilename, readBlobErrorMessage } from '@/lib/downloadBlobFile';

export async function fetchAuthenticatedPdfBlob(
  url: string,
  errorFallback: string,
  fallbackFilename: string,
): Promise<Blob> {
  const res = await api.get<Blob>(url, {
    responseType: 'blob',
    params: { t: Date.now() },
    headers: {
      Accept: 'application/pdf, application/json',
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache',
    },
    validateStatus: (status) => status >= 200 && status < 500,
  });
  return resolvePdfBlobResponse(res, errorFallback, fallbackFilename);
}

async function resolvePdfBlobResponse(
  res: AxiosResponse<Blob>,
  errorFallback: string,
  fallbackFilename: string,
): Promise<Blob> {
  const contentType = String(res.headers['content-type'] || '');
  const isJson =
    contentType.includes('application/json') ||
    (res.data instanceof Blob && res.data.type.includes('json'));
  if (res.status >= 400 || isJson) {
    const msg = await readBlobErrorMessage(res.data, errorFallback);
    throw Object.assign(new Error(msg), { response: res });
  }
  if (!(res.data instanceof Blob) || !res.data.size) {
    throw new Error('O PDF retornado está vazio.');
  }
  const filename =
    parseContentDispositionFilename(res.headers['content-disposition']) || fallbackFilename;
  void filename;
  return res.data;
}
