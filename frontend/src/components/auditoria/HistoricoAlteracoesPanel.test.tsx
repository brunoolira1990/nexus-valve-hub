import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';
import { auditoriaService } from '@/services/api/auditoria';
import { AUDITORIA_VALOR_PROTEGIDO } from '@/lib/auditoriaHistorico';

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    historicoObjeto: vi.fn(),
    capacidade: vi.fn(),
  },
}));

describe('HistoricoAlteracoesPanel', () => {
  beforeEach(() => {
    vi.mocked(auditoriaService.historicoObjeto).mockReset();
  });

  it('não carrega histórico enquanto a aba não está ativa', () => {
    render(
      <HistoricoAlteracoesPanel
        appLabel="cadastros"
        modelName="cliente"
        objectId={10}
        active={false}
        enabled
      />,
    );
    expect(auditoriaService.historicoObjeto).not.toHaveBeenCalled();
  });

  it('lazy-load ao ativar e exibe estado vazio', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    render(
      <HistoricoAlteracoesPanel
        appLabel="cadastros"
        modelName="cliente"
        objectId={10}
        active
        enabled
      />,
    );
    await waitFor(() => expect(auditoriaService.historicoObjeto).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('auditoria-historico-vazio')).toBeInTheDocument();
  });

  it('lista CREATE e UPDATE com campo protegido', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 2,
          operacao: 'UPDATE',
          ator: { id: 1, nome: 'Operador' },
          criado_em: '2026-07-24T12:00:00Z',
          alteracoes: {
            email: { sensivel: true, alterado: true },
            nome_fantasia: { antes: 'A', depois: 'B' },
          },
        },
        {
          id: 1,
          operacao: 'CREATE',
          ator: { id: 1, nome: 'Operador' },
          criado_em: '2026-07-24T11:00:00Z',
          alteracoes: { razao_social: { antes: null, depois: 'Cliente X' } },
        },
      ],
    });
    render(
      <HistoricoAlteracoesPanel
        appLabel="cadastros"
        modelName="cliente"
        objectId={10}
        active
        enabled
      />,
    );
    expect(await screen.findByTestId('auditoria-evento-2')).toHaveAttribute('data-operacao', 'UPDATE');
    expect(screen.getByTestId('auditoria-evento-1')).toHaveAttribute('data-operacao', 'CREATE');
    expect(screen.getByTestId('auditoria-campo-email')).toHaveTextContent(AUDITORIA_VALOR_PROTEGIDO);
    expect(screen.getByTestId('auditoria-campo-nome_fantasia')).toHaveTextContent('de A para B');
    expect(screen.queryByRole('button', { name: /excluir|editar/i })).not.toBeInTheDocument();
  });

  it('exibe erro 403 amigável', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockRejectedValue({
      response: { status: 403, data: { detail: 'Forbidden' } },
      isAxiosError: true,
    });
    render(
      <HistoricoAlteracoesPanel
        appLabel="produtos"
        modelName="produto"
        objectId={5}
        active
        enabled
      />,
    );
    expect(await screen.findByTestId('auditoria-historico-forbidden')).toBeInTheDocument();
  });

  it('exibe erro de rede amigável', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockRejectedValue(new Error('Network Error'));
    render(
      <HistoricoAlteracoesPanel
        appLabel="produtos"
        modelName="produto"
        objectId={5}
        active
        enabled
      />,
    );
    expect(await screen.findByTestId('auditoria-historico-erro')).toBeInTheDocument();
  });

  it('não renderiza painel quando enabled=false', () => {
    const { container } = render(
      <HistoricoAlteracoesPanel
        appLabel="cadastros"
        modelName="cliente"
        objectId={10}
        active
        enabled={false}
      />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(auditoriaService.historicoObjeto).not.toHaveBeenCalled();
  });
});
