import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RegrasFiscais from '@/pages/RegrasFiscais';
import { ChecklistFiscalMinimo } from '@/components/fiscal/ChecklistFiscalMinimo';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';

vi.mock('@/components/RegrasFiscaisSaidaTab', () => ({
  RegrasFiscaisSaidaTab: () => <div>Saída tab</div>,
}));
vi.mock('@/components/RegrasFiscaisLegadoTab', () => ({
  RegrasFiscaisLegadoTab: () => <div>Legado tab</div>,
}));
vi.mock('@/components/RegrasFiscaisEntradaTab', () => ({
  RegrasFiscaisEntradaTab: () => <div>Entrada tab</div>,
}));

describe('RegrasFiscais 401410', () => {
  beforeEach(() => {
    vi.spyOn(regrasFiscaisService, 'checklistProducao').mockResolvedValue({
      checklist_fiscal: [
        { item: 'Empresa com regime tributário', ok: false, nota: '' },
        { item: 'Regra fiscal de venda ativa', ok: false, nota: '' },
      ],
      criticos: [{ mensagem: 'Nenhuma regra fiscal cadastrada.' }],
      metricas: { regras_total: 0 },
    });
  });

  it('exibe checklist fiscal mínimo', async () => {
    render(
      <MemoryRouter>
        <RegrasFiscais />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Checklist fiscal mínimo para produção/i)).toBeInTheDocument();
      expect(screen.getByText(/Regra fiscal de venda ativa/i)).toBeInTheDocument();
    });
  });
});

describe('ChecklistFiscalMinimo', () => {
  it('mostra críticos fiscais', async () => {
    vi.spyOn(regrasFiscaisService, 'checklistProducao').mockResolvedValue({
      checklist_fiscal: [],
      criticos: [{ mensagem: 'Nenhuma regra fiscal ativa cadastrada.' }],
    });
    render(<ChecklistFiscalMinimo />);
    await waitFor(() => {
      expect(screen.getByText(/Nenhuma regra fiscal ativa/i)).toBeInTheDocument();
    });
  });
});
