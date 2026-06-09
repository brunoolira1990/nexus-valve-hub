import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { formatPeriodoLabel, navItemsForPermissoes } from '@/components/bi/dashboardBiConfig';
import { BIPreparationState } from '@/components/bi/BIPreparationState';
import { BIEmptyChart } from '@/components/bi/BIEmptyChart';

describe('ERP 4.0.8.1 — período pt-BR', () => {
  it('formata mês atual em português', () => {
    const label = formatPeriodoLabel({
      data_inicio: '2026-05-01',
      data_fim: '2026-05-23',
      label: 'May/2026',
      periodo: 'mes_atual',
      empresa_id: null,
      status: null,
    });
    expect(label).toBe('Maio/2026');
    expect(label).not.toMatch(/MAY|May/i);
  });

  it('formata período personalizado', () => {
    const label = formatPeriodoLabel({
      data_inicio: '2026-05-01',
      data_fim: '2026-05-24',
      label: '2026-05-01 — 2026-05-24',
      periodo: 'personalizado',
      empresa_id: null,
      status: null,
    });
    expect(label).toBe('01/05/2026 a 24/05/2026');
  });
});

describe('ERP 4.0.8.1 — navegação por permissão', () => {
  it('menu mostra só módulos permitidos', () => {
    const items = navItemsForPermissoes({
      pode_ver_comercial: true,
      pode_ver_fiscal: false,
      pode_ver_estoque: false,
      pode_ver_compras: false,
      pode_ver_qualidade: false,
      pode_ver_financeiro: false,
      pode_ver_consolidado: false,
    });
    const labels = items.map((i) => i.label);
    expect(labels).toContain('Comercial');
    expect(labels).not.toContain('Fiscal');
    expect(labels).toContain('Visão geral');
  });
});

describe('ERP 4.0.8.1 — BIPreparationState', () => {
  it('BIPreparationState não exibe R$ 0,00', () => {
    render(<BIPreparationState />);
    expect(screen.getByText('Financeiro em preparação')).toBeInTheDocument();
    expect(screen.queryByText(/R\$\s*0,00/)).not.toBeInTheDocument();
  });
});

describe('ERP 4.0.8.1 — estado vazio compacto', () => {
  it('BIEmptyChart é compacto', () => {
    const { container } = render(<BIEmptyChart title="Sem NF-e no período" message="Nenhuma nota encontrada." />);
    expect(container.querySelector('.max-h-\\[160px\\]')).toBeTruthy();
  });
});
