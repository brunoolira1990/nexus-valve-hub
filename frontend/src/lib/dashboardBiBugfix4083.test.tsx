import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AxiosError } from 'axios';

import { useDashboardBI } from '@/hooks/useDashboardBI';
import { useDashboardPermissoes } from '@/hooks/useDashboardPermissoes';
import { BIAccessDenied } from '@/components/bi/BIAccessDenied';
import { BIErrorState } from '@/components/bi/BIErrorState';
import { BIKpiHeroCard } from '@/components/bi/BIKpiHeroCard';
import { BIChartCard } from '@/components/bi/BIChartCard';
import { formatPeriodoLabel } from '@/components/bi/dashboardBiConfig';
import { hasChartData, normalizeChartData } from '@/lib/biChartData';
import { SESSION_EXPIRED_MESSAGE } from '@/services/api/config';
import { dashboardService } from '@/services/api/dashboard';
import { clearDashboardPermissoesCache } from '@/services/api/dashboardPermissoesCache';

vi.mock('@/services/api/dashboard', () => ({
  dashboardService: {
    getPermissoes: vi.fn(),
    getComercial: vi.fn(),
    getFiscal: vi.fn(),
    getEstoque: vi.fn(),
    getCompras: vi.fn(),
    getQualidade: vi.fn(),
    getFinanceiro: vi.fn(),
    getHome: vi.fn(),
    getResumo: vi.fn(),
  },
}));

function axiosError(status: number): AxiosError {
  return new AxiosError('err', undefined, undefined, undefined, {
    status,
    data: { detail: status === 403 ? 'Forbidden' : 'Unauthorized' },
    statusText: '',
    headers: {},
    config: {} as never,
  });
}

describe('ERP 4.0.8.3 — tratamento 401/403', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearDashboardPermissoesCache();
  });

  it('useDashboardBI trata 401 sem rejeitar silenciosamente', async () => {
    vi.mocked(dashboardService.getComercial).mockRejectedValue(axiosError(401));

    const { result } = renderHook(
      () => useDashboardBI('comercial', dashboardService.getComercial),
      { wrapper: ({ children }) => <MemoryRouter>{children}</MemoryRouter> },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.unauthorized).toBe(true);
    expect(result.current.error).toBe(SESSION_EXPIRED_MESSAGE);
    expect(result.current.data).toBeNull();
  });

  it('useDashboardBI trata 403 com forbidden', async () => {
    vi.mocked(dashboardService.getFiscal).mockRejectedValue(axiosError(403));

    const { result } = renderHook(
      () => useDashboardBI('fiscal', dashboardService.getFiscal),
      { wrapper: ({ children }) => <MemoryRouter>{children}</MemoryRouter> },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.forbidden).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('useDashboardPermissoes trata 401 com fallback seguro', async () => {
    vi.mocked(dashboardService.getPermissoes).mockRejectedValue(axiosError(401));

    const { result } = renderHook(() => useDashboardPermissoes());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.permissoes.pode_ver_comercial).toBe(false);
    expect(result.current.unauthorized).toBe(true);
  });

  it('BIErrorState exibe mensagem de sessão', () => {
    render(<BIErrorState message={SESSION_EXPIRED_MESSAGE} />);
    expect(screen.getByText(/sessão expirada/i)).toBeInTheDocument();
  });

  it('BIAccessDenied exibe acesso negado', () => {
    render(
      <MemoryRouter>
        <BIAccessDenied modulo="Fiscal" message="Você não tem permissão para acessar este painel." />
      </MemoryRouter>,
    );
    expect(screen.getByText(/acesso restrito/i)).toBeInTheDocument();
    expect(screen.getByText(/não tem permissão/i)).toBeInTheDocument();
  });
});

describe('ERP 4.0.8.3 — período e gráficos', () => {
  it('formatPeriodoLabel aceita null/undefined', () => {
    expect(formatPeriodoLabel(null)).toBe('');
    expect(formatPeriodoLabel(undefined)).toBe('');
  });

  it('hasChartData retorna false para dados vazios', () => {
    expect(hasChartData([])).toBe(false);
    expect(hasChartData([{ value: 0 }])).toBe(false);
    expect(hasChartData([{ value: 1 }])).toBe(true);
  });

  it('normalizeChartData trata undefined', () => {
    expect(normalizeChartData(undefined)).toEqual([]);
    expect(normalizeChartData({ id: 'x', titulo: 'T', tipo: 'bar', dados: [] })).toEqual([]);
  });

  it('BIChartCard exibe BIEmptyChart sem dados', () => {
    render(
      <BIChartCard
        chart={{ id: 'c1', titulo: 'Teste', tipo: 'bar', dados: [] }}
        emptyTitle="Sem dados no período"
      />,
    );
    expect(screen.getByText('Sem dados no período')).toBeInTheDocument();
  });

  it('BIChartCard wrapper tem altura mínima definida', () => {
    const { container } = render(
      <BIChartCard chart={{ id: 'c2', titulo: 'Com dados', tipo: 'bar', dados: [{ label: 'A', valor: 10 }] }} />,
    );
    expect(container.querySelector('.min-h-\\[280px\\]')).toBeTruthy();
    expect(container.querySelector('.h-\\[320px\\]')).toBeTruthy();
  });
});

describe('ERP 4.0.8.3 — KPI Hero', () => {
  it('BIKpiHeroCard renderiza R$ 500,00 sem truncar', () => {
    render(
      <BIKpiHeroCard
        kpi={{
          id: 'valor_aberto',
          titulo: 'Valor a faturar',
          valor: '500',
          formato: 'moeda',
        }}
      />,
    );
    expect(screen.getByText('Valor a faturar')).toBeInTheDocument();
    expect(screen.getByText(/R\$\s*500,00/)).toBeInTheDocument();
    const valueEl = screen.getByText(/R\$\s*500,00/);
    expect(valueEl.className).toMatch(/break-words/);
  });
});

describe('ERP 4.0.8.3 — financeiro operacional', () => {
  it('payload operacional não quebra normalizeChartData', async () => {
    vi.mocked(dashboardService.getFinanceiro).mockResolvedValue({
      modulo: 'financeiro',
      periodo: {
        data_inicio: '2026-05-01',
        data_fim: '2026-05-23',
        label: 'Maio/2026',
        periodo: 'mes_atual',
        empresa_id: null,
        status: null,
      },
      kpis: [
        { id: 'saldo_previsto', titulo: 'Saldo previsto', valor: '100.00', formato: 'moeda' },
      ],
      graficos: [],
      rankings: [],
      alertas: [],
      ultimos: [],
      links: [{ id: 'visao', titulo: 'Visão', descricao: '', link: '/financeiro' }],
      em_preparacao: false,
    });

    const { result } = renderHook(
      () => useDashboardBI('financeiro', dashboardService.getFinanceiro),
      { wrapper: ({ children }) => <MemoryRouter>{children}</MemoryRouter> },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data?.em_preparacao).toBe(false);
    expect(result.current.error).toBeNull();
  });
});
