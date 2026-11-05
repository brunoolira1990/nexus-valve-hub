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
    expect(screen.getByTestId('auditoria-antes-nome_fantasia')).toHaveTextContent('A');
    expect(screen.getByTestId('auditoria-depois-nome_fantasia')).toHaveTextContent('B');
    expect(screen.getByTestId('auditoria-campo-nome_fantasia')).not.toHaveTextContent('de A para B');
    // CREATE não tem valor anterior: mostra apenas o badge verde do valor novo.
    expect(screen.queryByTestId('auditoria-antes-razao_social')).not.toBeInTheDocument();
    expect(screen.getByTestId('auditoria-depois-razao_social')).toHaveTextContent('Cliente X');
    expect(screen.queryByRole('button', { name: /excluir|editar/i })).not.toBeInTheDocument();
  });

  it('mostra o nome resolvido pelo backend em vez do id ou do código cru', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 9,
          operacao: 'UPDATE',
          ator: { id: 1, nome: 'Operador' },
          criado_em: '2026-07-24T12:00:00Z',
          alteracoes: {
            familia_id: {
              antes: { valor: 94, id: 94, nome: '0049 — FLANGE CEGO INOX 304' },
              depois: { valor: 95, id: 95, nome: '0050 — FLANGE CEGO CARBONO' },
            },
            tipo_controle_unidade: {
              antes: { valor: 'PECA', id: null, nome: 'Peça' },
              depois: 'UNITARIO',
            },
            material: {
              antes: null,
              depois: { valor: 'ACO CARBONO', id: 3, nome: 'Aço Carbono' },
            },
          },
        },
      ],
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
    expect(await screen.findByTestId('auditoria-antes-familia_id')).toHaveTextContent(
      '0049 — FLANGE CEGO INOX 304',
    );
    expect(screen.getByTestId('auditoria-depois-familia_id')).not.toHaveTextContent('94');
    expect(screen.getByTestId('auditoria-antes-tipo_controle_unidade')).toHaveTextContent('Peça');
    // valor não resolvido pelo backend permanece cru, sem inventar rótulo.
    expect(screen.getByTestId('auditoria-depois-tipo_controle_unidade')).toHaveTextContent('UNITARIO');
    expect(screen.getByTestId('auditoria-depois-material')).toHaveTextContent('Aço Carbono');
    expect(screen.getByTestId('auditoria-depois-material')).not.toHaveTextContent('ACO CARBONO');
  });

  it('renderiza acao != "" como EVENTO, ignora chaves reservadas "_" e não mostra diff de campo', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 11,
          operacao: 'UPDATE',
          acao: 'conferir',
          ator: { id: 1, nome: 'Fiscal' },
          criado_em: '2026-11-04T12:00:00Z',
          alteracoes: {
            status: { antes: 'PENDENTE', depois: 'CONFERIDA' },
            // O payload real do PR 1 guarda dict cru sob as chaves reservadas '_' — fora do
            // tipo fechado AuditoriaCampoAlteracao de propósito: o parser as descarta.
            _snapshot: { status: 'CONFERIDA' },
            _detalhes: { itens: 2 },
          } as never,
        },
      ],
    });
    render(
      <HistoricoAlteracoesPanel appLabel="fiscal" modelName="nfeentradaconferencia" objectId={7} active enabled />,
    );
    const li = await screen.findByTestId('auditoria-evento-11');
    expect(li).toHaveAttribute('data-acao', 'conferir');
    // EVENTO: ícone + label humano do ACAO_LABELS (não o badge 'Atualização').
    expect(screen.getByTestId('auditoria-acao-11')).toHaveTextContent('Conferiu a nota');
    // chaves '_' nunca viram diff de campo; e o evento não renderiza lista de campos.
    expect(screen.queryByTestId('auditoria-campo-_snapshot')).not.toBeInTheDocument();
    expect(screen.queryByTestId('auditoria-campo-_detalhes')).not.toBeInTheDocument();
    expect(screen.queryByTestId('auditoria-campo-status')).not.toBeInTheDocument();
  });

  it('acao ausente/vazia mantém o render atual de diff (retrocompatibilidade com fixtures pré-PR1)', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 12,
          operacao: 'UPDATE',
          ator: { id: 1, nome: 'Fiscal' },
          criado_em: '2026-11-04T12:00:00Z',
          alteracoes: {
            status: { antes: 'PENDENTE', depois: 'CONFERIDA' },
            _detalhes: { x: 1 },
          },
        } as never,
      ],
    });
    render(
      <HistoricoAlteracoesPanel appLabel="fiscal" modelName="nfeentradaconferencia" objectId={7} active enabled />,
    );
    const li = await screen.findByTestId('auditoria-evento-12');
    expect(li).not.toHaveAttribute('data-acao');
    expect(screen.getByTestId('auditoria-campo-status')).toHaveTextContent('CONFERIDA');
    expect(screen.getByTestId('auditoria-antes-status')).toHaveTextContent('PENDENTE');
    expect(screen.queryByTestId('auditoria-campo-_detalhes')).not.toBeInTheDocument();
  });

  it('acao desconhecida cai no fallback legível (snake_case lido), sem inventar label', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 13,
          operacao: 'UPDATE',
          acao: 'reprocessar_lote_extraordinario',
          ator: { id: 1, nome: 'Sistema' },
          criado_em: '2026-11-04T12:00:00Z',
          alteracoes: {},
        },
      ],
    });
    render(
      <HistoricoAlteracoesPanel appLabel="fiscal" modelName="nfeentradaconferencia" objectId={7} active enabled />,
    );
    expect(await screen.findByTestId('auditoria-acao-13')).toHaveTextContent('reprocessar lote extraordinario');
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
