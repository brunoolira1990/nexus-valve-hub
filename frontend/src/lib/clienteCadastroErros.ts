/**
 * Mensagens de gravação do cadastro de Cliente (validação DRF).
 * Não altera unicidade de CNPJ — só interpreta a resposta HTTP 400.
 */
import type { AxiosError } from 'axios';
import { normalizeCnpj } from '@/lib/cnpj';
import { apiErrorMessage, getApiErrorStatus, SESSION_EXPIRED_MESSAGE, PERMISSION_DENIED_MESSAGE } from '@/services/api/config';
import { clientesService } from '@/services/api/clientes';
import type { Cliente } from '@/types';

export const MSG_CNPJ_CLIENTE_DUPLICADO = 'Já existe um cliente cadastrado com este CNPJ.';
/** Orientação secundária quando não há link seguro (zero/múltiplos matches). */
export const MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM =
  'Busque pelo CNPJ na listagem de clientes.';

const CNPJ_DUPLICATE_RE = /já existe|already exists|unique|duplicad/i;

export type ClienteSaveErrorInfo = {
  message: string;
  cnpjError: string | null;
  isCnpjDuplicate: boolean;
  status?: number;
};

function fieldMessages(data: Record<string, unknown>, field: string): string[] {
  const raw = data[field];
  if (Array.isArray(raw)) return raw.map(String).map((s) => s.trim()).filter(Boolean);
  if (typeof raw === 'string' && raw.trim()) return [raw.trim()];
  return [];
}

function looksLikeCnpjDuplicate(text: string): boolean {
  const t = text.toLowerCase();
  return t.includes('cnpj') && CNPJ_DUPLICATE_RE.test(t);
}

/** Interpreta erro de create/update de cliente para a UI (sem vazar payload bruto). */
export function parseClienteSaveError(err: unknown): ClienteSaveErrorInfo {
  const status = getApiErrorStatus(err);
  if (status === 401) {
    return { message: SESSION_EXPIRED_MESSAGE, cnpjError: null, isCnpjDuplicate: false, status };
  }
  if (status === 403) {
    return { message: PERMISSION_DENIED_MESSAGE, cnpjError: null, isCnpjDuplicate: false, status };
  }
  if (status != null && status >= 500) {
    return {
      message: 'Erro interno do servidor. Tente novamente em instantes.',
      cnpjError: null,
      isCnpjDuplicate: false,
      status,
    };
  }

  const data = (err as AxiosError<Record<string, unknown>>)?.response?.data;
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const cnpjMsgs = fieldMessages(data, 'cnpj');
    if (cnpjMsgs.some((m) => CNPJ_DUPLICATE_RE.test(m) || looksLikeCnpjDuplicate(m))) {
      return {
        message: MSG_CNPJ_CLIENTE_DUPLICADO,
        cnpjError: MSG_CNPJ_CLIENTE_DUPLICADO,
        isCnpjDuplicate: true,
        status,
      };
    }
    if (cnpjMsgs.length) {
      return {
        message: cnpjMsgs[0],
        cnpjError: cnpjMsgs[0],
        isCnpjDuplicate: false,
        status,
      };
    }
    for (const key of ['detail', 'mensagem', 'non_field_errors'] as const) {
      const msgs = fieldMessages(data, key);
      if (msgs.some(looksLikeCnpjDuplicate)) {
        return {
          message: MSG_CNPJ_CLIENTE_DUPLICADO,
          cnpjError: MSG_CNPJ_CLIENTE_DUPLICADO,
          isCnpjDuplicate: true,
          status,
        };
      }
    }
  }

  const message = apiErrorMessage(err, {
    fallback: 'Não foi possível salvar o cliente. Verifique os dados e tente novamente.',
  });
  return {
    message,
    cnpjError: null,
    isCnpjDuplicate: looksLikeCnpjDuplicate(message),
    status,
  };
}

/**
 * Localiza o cliente existente pelo CNPJ normalizado.
 * Só retorna ID quando há exatamente um match exato — evita abrir o cadastro errado.
 */
export async function encontrarClienteIdPorCnpjExato(cnpj: string): Promise<number | null> {
  const digits = normalizeCnpj(cnpj);
  if (digits.length !== 14) return null;
  const results = await clientesService.search(digits, 10);
  const matches = results.filter((c: Cliente) => normalizeCnpj(c.cnpj) === digits);
  if (matches.length !== 1 || matches[0].id == null) return null;
  return Number(matches[0].id);
}
