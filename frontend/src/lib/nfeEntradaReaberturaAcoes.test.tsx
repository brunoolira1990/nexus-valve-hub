import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CentralDfeWorkspaceSheet } from '@/components/fiscal/CentralDfeWorkspaceSheet';
import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';
import type { CentralDfeDocumento } from '@/services/api/centralDfe';
import type { NFeEntradaConferencia } from '@/types';

const mocks = vi.hoisted(() => ({
  getConferencia: vi.fn(),
}));

vi.mock('@/services/api/nfeEntradaConferencia', () => ({
  nfeEntradaConferenciaService: {
    get: mocks.getConferencia,
    previewReabertura: vi.fn(),
    reabrir: vi.fn(),
  },
}));

vi.mock('@/services/api/comercial', () => ({
  pedidosCompraService: { getAll: vi.fn().mockResolvedValue([]) },
}));

vi.mock('@/services/api/produtos', () => ({
  produtosService: {
    search: vi.fn().mockResolvedValue([]),
    getById: vi.fn(),
  },
}));

const conf = {
  id: 20,
  nf_entrada_historica: 10,
  numero: '123',
  serie: '1',
  data_emissao: '2026-07-01',
  data_entrada: '2026-07-02',
  valor_total: 100,
  fornecedor_nome: 'Fornecedor teste',
  fornecedor_cnpj: '00000000000191',
  status: 'PREPARADA',
  divergencias_aceitas: false,
  estoque_aplicado_em: null,
  itens: [],
} satisfies NFeEntradaConferencia;

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ações de reabertura da entrada de fornecedor', () => {
  it('exibe a ação na tela de conferência', async () => {
    mocks.getConferencia.mockResolvedValue(conf);
    render(
      <MemoryRouter future={routerFuture}>
        <NFeEntradaConferenciaPanel nfeHistoricaId={10} />
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole('button', { name: /Reabrir entrada para correção/i }),
    ).toBeInTheDocument();
  });

  it('exibe a ação no resumo final da Central DF-e', async () => {
    mocks.getConferencia.mockResolvedValue(conf);
    const row = {
      id: 10,
      tipo_documento: 'NFE_ENTRADA',
      tipo_label: 'NF-e Fornecedor',
      chave_acesso: '1'.repeat(44),
      chave_resumida: '1111…1111',
      numero: '123',
      serie: '1',
      data_emissao: '2026-07-01',
      emitente_nome: 'Fornecedor teste',
      valor_total: '100.00',
      estado_consolidado: 'CONCLUIDO',
      estado_consolidado_label: 'Concluído',
      status_entrada: 'CONCLUIDO',
      status_entrada_label: 'Concluído',
      nf_entrada_historica_id: 10,
      xml_armazenado: true,
      detalhe_rota: '/nfe-entrada-historica-importada',
    } as CentralDfeDocumento;

    render(
      <MemoryRouter future={routerFuture}>
        <CentralDfeWorkspaceSheet
          open
          row={row}
          manifestacao={null}
          somenteResumo
          loadingAcao={false}
          onClose={vi.fn()}
          onUpdated={vi.fn().mockResolvedValue(undefined)}
          onPrepararManifestacao={vi.fn().mockResolvedValue(null)}
          onExecutarManifestacao={vi.fn().mockResolvedValue(undefined)}
          onIniciarArmazenarXmlNfe={vi.fn()}
          onIniciarArmazenarXmlCte={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole('button', { name: /Reabrir entrada para correção/i }),
    ).toBeInTheDocument();
  });
});
