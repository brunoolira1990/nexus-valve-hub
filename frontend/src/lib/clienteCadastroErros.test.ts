import { describe, expect, it, vi, beforeEach } from 'vitest';
import { AxiosError } from 'axios';
import {
  MSG_CNPJ_CLIENTE_DUPLICADO,
  MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM,
  encontrarClienteIdPorCnpjExato,
  parseClienteSaveError,
} from '@/lib/clienteCadastroErros';
import {
  apiErrorMessage,
  PERMISSION_DENIED_MESSAGE,
  SESSION_EXPIRED_MESSAGE,
} from '@/services/api/config';

vi.mock('@/services/api/clientes', () => ({
  clientesService: {
    search: vi.fn(),
  },
}));

import { clientesService } from '@/services/api/clientes';

function axiosErr(status: number, data: unknown, message = `Request failed with status code ${status}`) {
  const err = new AxiosError(message);
  err.response = {
    status,
    data,
    statusText: String(status),
    headers: {},
    config: {} as never,
  };
  return err;
}

describe('apiErrorMessage — validação DRF vs ruído Axios', () => {
  it('não mascara campo cnpj com Request failed with status code 400', () => {
    const err = axiosErr(400, { cnpj: ['Cliente com este CNPJ já existe.'] });
    expect(apiErrorMessage(err)).toBe('Cliente com este CNPJ já existe.');
    expect(apiErrorMessage(err)).not.toMatch(/Request failed/i);
  });

  it('lê detail, mensagem e non_field_errors', () => {
    expect(apiErrorMessage(axiosErr(400, { detail: 'Operação inválida.' }))).toBe('Operação inválida.');
    expect(apiErrorMessage(axiosErr(400, { mensagem: 'Falha de negócio.' }))).toBe('Falha de negócio.');
    expect(
      apiErrorMessage(axiosErr(400, { non_field_errors: ['Combinação inválida.'] })),
    ).toBe('Combinação inválida.');
  });

  it('lê campo como string isolada', () => {
    expect(apiErrorMessage(axiosErr(400, { cnpj: 'CNPJ inválido.' }))).toBe('CNPJ inválido.');
    expect(apiErrorMessage(axiosErr(400, { cnpj: 'CNPJ inválido.' }))).not.toMatch(/Request failed/i);
  });

  it('HTTP 409 com detail amigável', () => {
    expect(
      apiErrorMessage(axiosErr(409, { detail: 'Este cliente possui vínculo e não pode ser excluído.' })),
    ).toBe('Este cliente possui vínculo e não pode ser excluído.');
  });

  it('erro de rede sem response usa fallback amigável', () => {
    const err = new AxiosError('Network Error');
    // sem response
    expect(apiErrorMessage(err, { fallback: 'Não foi possível concluir a operação.' })).toBe(
      'Não foi possível concluir a operação.',
    );
    expect(apiErrorMessage(err)).not.toMatch(/Request failed/i);
    expect(apiErrorMessage(err)).not.toMatch(/\[object Object\]/i);
  });

  it('preserva 401 e 403', () => {
    expect(apiErrorMessage(axiosErr(401, { detail: 'x' }))).toBe(SESSION_EXPIRED_MESSAGE);
    expect(apiErrorMessage(axiosErr(403, { detail: 'x' }))).toBe(PERMISSION_DENIED_MESSAGE);
  });

  it('500 não vira mensagem de campo', () => {
    expect(apiErrorMessage(axiosErr(500, { cnpj: ['Cliente com este CNPJ já existe.'] }))).toMatch(
      /Erro interno/i,
    );
  });

  it('não retorna Request failed quando há corpo DRF útil', () => {
    const cases = [
      axiosErr(400, { detail: 'X' }),
      axiosErr(400, { mensagem: 'Y' }),
      axiosErr(400, { non_field_errors: ['Z'] }),
      axiosErr(400, { campo: ['A'] }),
      axiosErr(409, { detail: 'Conflito.' }),
    ];
    for (const err of cases) {
      expect(apiErrorMessage(err)).not.toMatch(/Request failed with status code/i);
    }
  });
});

describe('parseClienteSaveError', () => {
  it('traduz CNPJ duplicado do DRF para mensagem amigável', () => {
    const parsed = parseClienteSaveError(
      axiosErr(400, { cnpj: ['Cliente com este CNPJ já existe.'] }),
    );
    expect(parsed.message).toBe(MSG_CNPJ_CLIENTE_DUPLICADO);
    expect(parsed.cnpjError).toBe(MSG_CNPJ_CLIENTE_DUPLICADO);
    expect(parsed.isCnpjDuplicate).toBe(true);
  });

  it('não trata 401/403 como duplicidade', () => {
    expect(parseClienteSaveError(axiosErr(401, {})).isCnpjDuplicate).toBe(false);
    expect(parseClienteSaveError(axiosErr(401, {})).message).toBe(SESSION_EXPIRED_MESSAGE);
    expect(parseClienteSaveError(axiosErr(403, {})).isCnpjDuplicate).toBe(false);
    expect(parseClienteSaveError(axiosErr(403, {})).message).toBe(PERMISSION_DENIED_MESSAGE);
  });

  it('detail/mensagem/non_field_errors com CNPJ duplicado', () => {
    expect(
      parseClienteSaveError(axiosErr(400, { detail: 'Cliente com este CNPJ já existe.' })).isCnpjDuplicate,
    ).toBe(true);
    expect(
      parseClienteSaveError(axiosErr(400, { mensagem: 'CNPJ já existe no cadastro.' })).cnpjError,
    ).toBe(MSG_CNPJ_CLIENTE_DUPLICADO);
    expect(
      parseClienteSaveError(
        axiosErr(400, { non_field_errors: ['Cliente com este CNPJ já existe.'] }),
      ).message,
    ).toBe(MSG_CNPJ_CLIENTE_DUPLICADO);
  });
});

describe('encontrarClienteIdPorCnpjExato', () => {
  beforeEach(() => {
    vi.mocked(clientesService.search).mockReset();
  });

  it('retorna id somente com match exato único', async () => {
    vi.mocked(clientesService.search).mockResolvedValue([
      { id: 42, cnpj: '04.252.011/0001-10', razao_social: 'A' } as never,
      { id: 99, cnpj: '00.000.000/0001-91', razao_social: 'B' } as never,
    ]);
    await expect(encontrarClienteIdPorCnpjExato('04252011000110')).resolves.toBe(42);
  });

  it('retorna null se houver ambiguidade ou nenhum match', async () => {
    vi.mocked(clientesService.search).mockResolvedValue([
      { id: 1, cnpj: '04252011000110', razao_social: 'A' } as never,
      { id: 2, cnpj: '04.252.011/0001-10', razao_social: 'B' } as never,
    ]);
    await expect(encontrarClienteIdPorCnpjExato('04252011000110')).resolves.toBeNull();

    vi.mocked(clientesService.search).mockResolvedValue([]);
    await expect(encontrarClienteIdPorCnpjExato('04252011000110')).resolves.toBeNull();
  });

  it('ignora resultado parcial que não bate nos 14 dígitos', async () => {
    vi.mocked(clientesService.search).mockResolvedValue([
      { id: 5, cnpj: '04252011000199', razao_social: 'Parcial' } as never,
    ]);
    await expect(encontrarClienteIdPorCnpjExato('04252011000110')).resolves.toBeNull();
  });
});

describe('mensagens auxiliares', () => {
  it('orientação de listagem é secundária e distinta da mensagem principal', () => {
    expect(MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM).toMatch(/listagem/i);
    expect(MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM).not.toBe(MSG_CNPJ_CLIENTE_DUPLICADO);
  });
});
