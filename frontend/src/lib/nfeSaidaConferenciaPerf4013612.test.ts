import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('@/services/api/config', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
  apiErrorMessage: (e: unknown) => String(e),
}));

import api from '@/services/api/config';
import { nfeSaidasService } from '@/services/api/fiscal';

describe('nfeSaidaConferencia perf 4013612', () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  it('abrir conferência usa modo abertura por padrão', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { nfe: { id: 13 }, checklist: null } });
    await nfeSaidasService.conferencia(13);
    expect(api.get).toHaveBeenCalledWith('nf-saidas/13/conferencia/', {
      params: { modo: 'abertura' },
    });
  });

  it('salvar conferência usa endpoint dedicado', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { conferencia: { nfe: { id: 13 } } } });
    await nfeSaidasService.salvarConferencia(13, { observacoes_internas: 'x' });
    expect(api.post).toHaveBeenCalledWith('nf-saidas/13/salvar-conferencia/', {
      observacoes_internas: 'x',
    });
  });

  it('salvar e validar usa endpoint combinado', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { mensagem: 'ok' } });
    await nfeSaidasService.salvarEValidarConferencia(13, { observacoes_internas: 'y' });
    expect(api.post).toHaveBeenCalledWith('nf-saidas/13/salvar-e-validar-conferencia/', {
      observacoes_internas: 'y',
    });
  });
});
