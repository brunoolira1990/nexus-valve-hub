import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { Badge } from '@/components/nexus/Badge';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NexusCard } from '@/components/nexus/NexusCard';
import { EmptyState } from '@/components/nexus/EmptyState';
import { ErrorState } from '@/components/nexus/ErrorState';
import { MainLayout } from '@/components/MainLayout';
import { Header } from '@/components/Header';
import { Sidebar } from '@/components/Sidebar';
import { resolveStatusToken } from '@/design-system/tokens';
import DashboardHome from '@/pages/dashboard/DashboardHome';

vi.mock('@/hooks/useDashboardPermissoes', () => ({
  useDashboardPermissoes: () => ({
    permissoes: { pode_ver_consolidado: true },
    loading: false,
  }),
}));

vi.mock('@/hooks/useDashboardBI', () => ({
  useDashboardHomeFilters: () => ({
    appliedFilters: {},
    applyFilters: vi.fn(),
    clearFilters: vi.fn(),
    queryParams: {},
  }),
}));

vi.mock('@/services/api/dashboard', () => ({
  dashboardService: {
    getHome: vi.fn().mockResolvedValue({
      periodo: {
        label: 'Maio/2026',
        periodo: 'mes_atual',
        data_inicio: '2026-05-01',
        data_fim: '2026-05-31',
        empresa_id: null,
        status: null,
      },
      permissoes: { pode_ver_consolidado: true },
      modulos: [],
      alertas: [],
    }),
  },
}));

describe('ERP 4.0.9 — Design System Nexus', () => {
  it('PageHeader renderiza título, descrição e ações', () => {
    render(
      <PageHeader title="Produtos" description="Cadastro de produtos." onAdd={vi.fn()} addLabel="Novo" />,
    );
    expect(screen.getByRole('heading', { name: 'Produtos' })).toBeInTheDocument();
    expect(screen.getByText('Cadastro de produtos.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /novo/i })).toBeInTheDocument();
  });

  it('NexusButton renderiza variantes', () => {
    render(
      <div>
        <NexusButton variant="default">Primary</NexusButton>
        <NexusButton variant="outline">Outline</NexusButton>
        <NexusButton variant="destructive">Danger</NexusButton>
        <NexusButton variant="success">Success</NexusButton>
      </div>,
    );
    expect(screen.getByRole('button', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Outline' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Danger' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Success' })).toBeInTheDocument();
  });

  it('StatusBadge mapeia status principais', () => {
    render(
      <div>
        <StatusBadge status="Rascunho" />
        <StatusBadge status="Autorizada homologação" />
        <StatusBadge status="Faturado" />
      </div>,
    );
    expect(screen.getByText('Rascunho')).toBeInTheDocument();
    expect(screen.getByText('Autorizada homologação')).toBeInTheDocument();
    expect(screen.getByText('Faturado')).toBeInTheDocument();
    expect(resolveStatusToken('Autorizada homologação').homologacao).toBe(true);
  });

  it('Badge e Card renderizam variantes', () => {
    render(
      <NexusCard title="KPI" subtitle="Resumo" variant="kpi">
        <Badge variant="success">Ativo</Badge>
      </NexusCard>,
    );
    expect(screen.getByText('KPI')).toBeInTheDocument();
    expect(screen.getByText('Ativo')).toBeInTheDocument();
  });

  it('EmptyState e ErrorState são amigáveis', () => {
    const onAction = vi.fn();
    render(<EmptyState title="Vazio" message="Sem itens" actionLabel="Criar" onAction={onAction} />);
    fireEvent.click(screen.getByRole('button', { name: 'Criar' }));
    expect(onAction).toHaveBeenCalled();

    render(<ErrorState message="Falha ao carregar." />);
    expect(screen.getByText('Falha ao carregar.')).toBeInTheDocument();
  });

  it('App shell renderiza sidebar e topbar', () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen onClose={vi.fn()} />
        <Header breadcrumbs={[{ label: 'Dashboard' }]} onToggleSidebar={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText('NEXUS APP')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sair/i })).toBeInTheDocument();
  });

  it('MainLayout renderiza outlet', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route path="dashboard" element={<div>Painel</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Painel')).toBeInTheDocument();
  });

  it('Dashboard continua renderizando', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <DashboardHome />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });
});
