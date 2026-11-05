import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UnifiedEntradaFeed } from '@/components/auditoria/UnifiedEntradaFeed';
import { auditoriaService, type AuditoriaHistoricoResponse, type RegistroAuditoria } from '@/services/api/auditoria';

vi.mock('@/services/api/auditoria', () => ({
  auditoriaService: {
    historicoObjeto: vi.fn(),
    capacidade: vi.fn(),
  },
}));

function registro(
  id: number,
  criado_em: string,
  extra: Partial<RegistroAuditoria> = {},
): RegistroAuditoria {
  return {
    id,
    operacao: 'UPDATE',
    ator: { id: 1, nome: 'Operador' },
    criado_em,
    alteracoes: {},
    ...extra,
  };
}

function resposta(results: RegistroAuditoria[]): AuditoriaHistoricoResponse {
  return { count: results.length, next: null, previous: null, results };
}

/** Roteia o mock pelo modelName — o feed chama as duas entidades no mesmo service. */
function rotear(registrosPorModelo: Record<string, RegistroAuditoria[]>) {
  vi.mocked(auditoriaService.historicoObjeto).mockImplementation(
    async (appLabel, modelName) => resposta(registrosPorModelo[modelName] ?? []),
  );
}

describe('UnifiedEntradaFeed', () => {
  beforeEach(() => {
    vi.mocked(auditoriaService.historicoObjeto).mockReset();
  });

  it('consulta conferência e histórica pelo mesmo caminho do Chatter', async () => {
    rotear({});
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);
    await waitFor(() => expect(auditoriaService.historicoObjeto).toHaveBeenCalledTimes(2));
    expect(auditoriaService.historicoObjeto).toHaveBeenCalledWith(
      'fiscal',
      'nfeentradaconferencia',
      10,
      { page_size: 50 },
    );
    expect(auditoriaService.historicoObjeto).toHaveBeenCalledWith(
      'fiscal',
      'nfeentradahistoricaimportada',
      7,
      { page_size: 50 },
    );
  });

  it('mescla registros das duas entidades em criado_em decrescente no mesmo container', async () => {
    rotear({
      nfeentradaconferencia: [
        registro(1, '2026-07-20T10:00:00Z', { alteracoes: { status: { antes: 'A', depois: 'B' } } }),
        registro(3, '2026-07-22T10:00:00Z'),
      ],
      nfeentradahistoricaimportada: [
        registro(2, '2026-07-21T10:00:00Z'),
        registro(4, '2026-07-23T10:00:00Z'),
      ],
    });
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);

    const lista = await screen.findByTestId('auditoria-feed-lista');
    const eventos = Array.from(lista.querySelectorAll('[data-testid^="auditoria-evento-"]'));
    expect(eventos.map((el) => el.getAttribute('data-testid'))).toEqual([
      'auditoria-evento-4', // historica — mais recente
      'auditoria-evento-3', // conferencia
      'auditoria-evento-2', // historica
      'auditoria-evento-1', // conferencia — mais antigo
    ]);
    // As duas fontes precisam estar dentro do MESMO <ol> do feed.
    expect(lista.querySelectorAll('[data-testid^="auditoria-evento-"]')).toHaveLength(4);
  });

  it('desempata por id quando o criado_em é idêntico entre as fontes', async () => {
    rotear({
      nfeentradaconferencia: [registro(5, '2026-07-21T10:00:00Z')],
      nfeentradahistoricaimportada: [registro(9, '2026-07-21T10:00:00Z')],
    });
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);
    const lista = await screen.findByTestId('auditoria-feed-lista');
    const eventos = Array.from(lista.querySelectorAll('[data-testid^="auditoria-evento-"]'));
    expect(eventos.map((el) => el.getAttribute('data-testid'))).toEqual([
      'auditoria-evento-9',
      'auditoria-evento-5',
    ]);
  });

  it('CASO PONTO CRÍTICO: evento financeiro gravado contra a HISTÓRICA aparece no rail da conferência', async () => {
    // O PR 3 grava gerar_contas_pagar em NFeEntradaHistoricaImportada; antes do
    // PR 4 o rail (Chatter com entityType nfeentradaconferencia) não o mostrava.
    rotear({
      nfeentradaconferencia: [registro(1, '2026-07-20T10:00:00Z', { acao: 'conferir' })],
      nfeentradahistoricaimportada: [
        registro(2, '2026-07-21T10:00:00Z', { acao: 'gerar_contas_pagar' }),
      ],
    });
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);

    await screen.findByTestId('auditoria-feed-lista');
    expect(await screen.findByText('Gerou contas a pagar')).toBeInTheDocument();
    expect(screen.getByText('Conferiu a nota')).toBeInTheDocument();
    // Render de EVENTO (PR 2): badge + label, sem diff de campos.
    const eventoHistorica = screen.getByTestId('auditoria-evento-2');
    expect(eventoHistorica).toHaveAttribute('data-acao', 'gerar_contas_pagar');
    expect(eventoHistorica.querySelector('[data-testid^="auditoria-campo-"]')).toBeNull();
  });

  it('falha de uma fonte não impede a outra de renderizar (degradação graciosa)', async () => {
    vi.mocked(auditoriaService.historicoObjeto).mockImplementation(
      async (_appLabel, modelName) => {
        if (modelName === 'nfeentradaconferencia') {
          throw new Error('boom');
        }
        return resposta([registro(2, '2026-07-21T10:00:00Z', { acao: 'gerar_contas_pagar' })]);
      },
    );
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);

    expect(await screen.findByTestId('auditoria-feed-erro-conferencia')).toBeInTheDocument();
    const lista = await screen.findByTestId('auditoria-feed-lista');
    expect(lista.querySelector('[data-testid="auditoria-evento-2"]')).not.toBeNull();
  });

  it('403 em uma fonte mostra a mensagem de permissão específica daquela fonte', async () => {
    const forbidden = Object.assign(new Error('forbidden'), { response: { status: 403 } });
    vi.mocked(auditoriaService.historicoObjeto).mockImplementation(
      async (_appLabel, modelName) => {
        if (modelName === 'nfeentradahistoricaimportada') {
          throw forbidden;
        }
        return resposta([registro(1, '2026-07-20T10:00:00Z')]);
      },
    );
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);

    expect(await screen.findByTestId('auditoria-feed-forbidden-historica')).toBeInTheDocument();
    expect(screen.getByTestId('auditoria-evento-1')).toBeInTheDocument();
  });

  it('sem id de nenhuma entidade orienta a salvar o registro', () => {
    render(<UnifiedEntradaFeed conferenceId={null} historicaId={null} />);
    expect(screen.getByTestId('auditoria-feed-sem-objeto')).toBeInTheDocument();
    expect(auditoriaService.historicoObjeto).not.toHaveBeenCalled();
  });

  it('estado vazio quando as duas fontes respondem sem registros', async () => {
    rotear({});
    render(<UnifiedEntradaFeed conferenceId={10} historicaId={7} />);
    expect(await screen.findByTestId('auditoria-feed-vazio')).toBeInTheDocument();
  });
});
