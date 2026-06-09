import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RelatorioTitulosTable } from '@/components/financeiro/relatorios/RelatorioTitulosTable';
import type { RelatorioLinhaTitulo } from '@/services/api/financeiro';

const linhaBase: RelatorioLinhaTitulo = {
  id: 1,
  vencimento: '2026-06-16',
  vencimento_exibicao: '2026-06-16',
  emissao: '2026-06-04',
  documento: 'CR-2026-000003',
  origem: 'NF-e nº 000000003',
  origem_tipo: 'NFE_SAIDA',
  valor_original: '150.00',
  valor_baixado: '0.00',
  saldo: '150.00',
  status: 'EM_ABERTO',
  status_label: 'Em aberto',
  origem_fiscal_cancelada: false,
  pode_baixar: true,
  cliente_nome: 'Cliente Teste',
};

describe('ERP 4.0.14.8 — exibição financeira', () => {
  it('relatório não mostra vencimento — para título com parcela', () => {
    render(
      <RelatorioTitulosTable linhas={[linhaBase]} modo="RECEBER" onAbrir={() => undefined} />,
    );
    expect(screen.getByText('16/06/2026')).toBeInTheDocument();
    const row = screen.getByText('CR-2026-000003').closest('tr');
    expect(row?.textContent).toContain('16/06/2026');
    expect(row?.textContent).not.toMatch(/Vencimento não informado/);
  });

  it('exibe número CR no padrão na coluna documento', () => {
    render(
      <RelatorioTitulosTable linhas={[linhaBase]} modo="RECEBER" onAbrir={() => undefined} />,
    );
    expect(screen.getByText('CR-2026-000003')).toBeInTheDocument();
  });

  it('exibe aviso quando vencimento ausente (legado)', () => {
    render(
      <RelatorioTitulosTable
        linhas={[
          {
            ...linhaBase,
            vencimento: '',
            vencimento_exibicao: null,
            vencimento_ausente: 'Vencimento não informado.',
          },
        ]}
        modo="RECEBER"
        onAbrir={() => undefined}
      />,
    );
    expect(screen.getByText('Vencimento não informado.')).toBeInTheDocument();
  });
});
