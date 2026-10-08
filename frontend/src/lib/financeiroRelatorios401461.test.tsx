import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RelatorioFiltrosPanel } from '@/components/financeiro/relatorios/RelatorioFiltrosPanel';
import {
  EMPTY_STATE_RELATORIO,
  linkVerTitulosRelatorio,
  relatorioFiltrosFromSearchParams,
  relatorioFiltrosToQuery,
} from '@/lib/relatorioFinanceiro';

const noopLists = { categorias: [], centros: [], contas: [] };

describe('RelatorioFiltrosPanel ERP 4.0.14.6.1', () => {
  it('exibe um único painel Filtros', () => {
    render(
      <RelatorioFiltrosPanel
        modo="RECEBER"
        filtros={relatorioFiltrosFromSearchParams(new URLSearchParams())}
        onChange={() => {}}
        {...noopLists}
      />,
    );
    expect(screen.getByText('Filtros')).toBeInTheDocument();
    expect(screen.queryByText('Filtros avançados')).not.toBeInTheDocument();
    expect(screen.queryByText('Filtros do relatório')).not.toBeInTheDocument();
  });

  it('Mais filtros recolhido por padrão', () => {
    render(
      <RelatorioFiltrosPanel
        modo="RECEBER"
        filtros={relatorioFiltrosFromSearchParams(new URLSearchParams())}
        onChange={() => {}}
        {...noopLists}
      />,
    );
    expect(screen.getByText('Mais filtros')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('ID do cliente')).not.toBeInTheDocument();
  });

  it('toggles incluir quitados e cancelados existem', () => {
    render(
      <RelatorioFiltrosPanel
        modo="PAGAR"
        filtros={relatorioFiltrosFromSearchParams(new URLSearchParams())}
        onChange={() => {}}
        {...noopLists}
      />,
    );
    expect(screen.getByLabelText(/Incluir quitados/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Incluir cancelados/i)).toBeInTheDocument();
  });

  it('expande Mais filtros ao clicar', () => {
    render(
      <RelatorioFiltrosPanel
        modo="CLIENTES"
        filtros={relatorioFiltrosFromSearchParams(new URLSearchParams())}
        onChange={() => {}}
        {...noopLists}
      />,
    );
    fireEvent.click(screen.getByText('Mais filtros'));
    expect(screen.getByLabelText(/Incluir registros sem saldo/i)).toBeInTheDocument();
  });
});

describe('relatorioFiltros flags URL', () => {
  it('serializa incluir_quitados e incluir_cancelados', () => {
    const q = relatorioFiltrosToQuery({
      ...relatorioFiltrosFromSearchParams(new URLSearchParams()),
      incluir_quitados: '1',
      incluir_cancelados: '1',
    });
    expect(q.incluir_quitados).toBe('1');
    expect(q.incluir_cancelados).toBe('1');
  });
});

describe('linkVerTitulosRelatorio', () => {
  it('abre contas a receber com cliente e filtros', () => {
    const f = relatorioFiltrosFromSearchParams(new URLSearchParams('vencimento=vencidos'));
    const to = linkVerTitulosRelatorio('receber', f, 99);
    expect(to).toContain('/financeiro/relatorios/contas-receber');
    expect(to).toContain('cliente=99');
    expect(to).toContain('vencimento=vencidos');
  });
});

describe('empty states relatórios', () => {
  it('mensagens padronizadas', () => {
    expect(EMPTY_STATE_RELATORIO['contas-receber']).toMatch(/título a receber/i);
    expect(EMPTY_STATE_RELATORIO['contas-pagar']).toMatch(/conta a pagar/i);
    expect(EMPTY_STATE_RELATORIO.clientes).toMatch(/cliente com saldo/i);
    expect(EMPTY_STATE_RELATORIO.categorias).toMatch(/categoria financeira/i);
  });
});
