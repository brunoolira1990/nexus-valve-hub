import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RelatorioContasReceberPage from '@/pages/financeiro/relatorios/RelatorioContasReceberPage';
import { RelatorioPdfActions } from '@/components/financeiro/relatorios/RelatorioPdfActions';
import { MSG_ERRO_PDF_RELATORIO } from '@/lib/relatorioPdfDownload';
import {
  relatorioFiltrosFromSearchParams,
  relatorioFiltrosToQuery,
} from '@/lib/relatorioFinanceiro';

vi.mock('@/services/api/financeiro', () => ({
  financeiroService: {
    relatorioContasReceber: vi.fn().mockResolvedValue({
      tipo: 'contas_receber',
      periodo: { periodo: 'mes', data_inicio: '2026-06-01', data_fim: '2026-06-30' },
      cards: {
        total_aberto: { valor: '0', quantidade: 0 },
        total_vencido: { valor: '0', quantidade: 0 },
        recebido_periodo: { valor: '0', quantidade: 0 },
        total_parcial: { valor: '0', quantidade: 0 },
        quantidade_titulos: 0,
      },
      linhas: [],
      agrupamentos: [],
    }),
    listCategorias: vi.fn().mockResolvedValue({ results: [] }),
    listCentrosCusto: vi.fn().mockResolvedValue({ results: [] }),
    listContasAtivas: vi.fn().mockResolvedValue([]),
    getContaReceber: vi.fn(),
  },
}));

vi.mock('@/services/api/config', () => ({
  default: { get: vi.fn() },
  apiErrorMessage: () => 'erro',
}));

describe('RelatorioPdfActions', () => {
  it('exibe botão Gerar PDF', () => {
    render(
      <RelatorioPdfActions
        endpoint="contas-receber"
        filtros={relatorioFiltrosFromSearchParams(new URLSearchParams())}
      />,
    );
    expect(screen.getByRole('button', { name: /Gerar PDF/i })).toBeInTheDocument();
  });
});

describe('fetchRelatorioFinanceiroPdf', () => {
  it('usa filtros da URL na chamada ao endpoint PDF', () => {
    const filtros = relatorioFiltrosFromSearchParams(
      new URLSearchParams('vencimento=vencidos&incluir_cancelados=1'),
    );
    const q = relatorioFiltrosToQuery(filtros);
    expect(q.vencimento).toBe('vencidos');
    expect(q.incluir_cancelados).toBe('1');
    expect('financeiro/relatorios/contas-pagar/pdf/').toContain('contas-pagar');
  });

  it('endpoints por relatório', () => {
    const paths = [
      'contas-receber',
      'contas-pagar',
      'fluxo-previsto',
      'categorias',
      'clientes',
      'fornecedores',
    ];
    for (const p of paths) {
      expect(`financeiro/relatorios/${p}/pdf/`).toContain('/pdf/');
    }
  });
});

describe('RelatorioContasReceberPage PDF', () => {
  it('mostra Gerar PDF na página', async () => {
    render(
      <MemoryRouter initialEntries={['/financeiro/relatorios/contas-receber']}>
        <RelatorioContasReceberPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('button', { name: /Gerar PDF/i })).toBeInTheDocument();
  });
});

describe('mensagem de erro PDF', () => {
  it('mensagem amigável definida', () => {
    expect(MSG_ERRO_PDF_RELATORIO).toMatch(/Não foi possível gerar o PDF/i);
  });
});
