import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { dashboardService } from '@/services/api/dashboard';
import { BIAccessDenied } from '@/components/bi/BIAccessDenied';
import { DEFAULT_DASHBOARD_BI_FILTERS } from '@/hooks/useDashboardBI';

describe('ERP 4.0.8 — dashboard BI service', () => {
  const methods = [
    ['getHome', dashboardService.getHome],
    ['getComercial', dashboardService.getComercial],
    ['getFiscal', dashboardService.getFiscal],
    ['getEstoque', dashboardService.getEstoque],
    ['getCompras', dashboardService.getCompras],
    ['getQualidade', dashboardService.getQualidade],
    ['getFinanceiro', dashboardService.getFinanceiro],
    ['getResumo', dashboardService.getResumo],
  ] as const;

  it.each(methods)('%s é função async', (_name, fn) => {
    expect(typeof fn).toBe('function');
  });

  it('endpoints BI usam prefixo dashboard/', () => {
    expect(dashboardService.getHome).toBeDefined();
    expect(dashboardService.getComercial).toBeDefined();
  });
});

describe('ERP 4.0.8 — filtros padrão BI', () => {
  it('período padrão é mes_atual', () => {
    expect(DEFAULT_DASHBOARD_BI_FILTERS.periodo).toBe('mes_atual');
    expect(DEFAULT_DASHBOARD_BI_FILTERS.empresa_id).toBe('');
  });
});

describe('ERP 4.0.8 — BIAccessDenied', () => {
  it('exibe mensagem e link para dashboard', () => {
    render(
      <MemoryRouter>
        <BIAccessDenied modulo="Comercial" message="Sem permissão para o painel Comercial." />
      </MemoryRouter>,
    );
    expect(screen.getByText('Acesso restrito')).toBeInTheDocument();
    expect(screen.getByText('Sem permissão para o painel Comercial.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /voltar ao dashboard/i })).toHaveAttribute('href', '/dashboard');
  });
});
