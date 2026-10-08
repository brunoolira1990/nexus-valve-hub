import { describe, expect, it } from 'vitest';
import { buildPdfFilename } from './commercialPdfDownload';

describe('buildPdfFilename', () => {
  it('monta nome com número do pedido de venda', () => {
    expect(buildPdfFilename('pedido-venda', 'PV-20260521-0001', 99)).toBe(
      'pedido-venda-PV-20260521-0001.pdf',
    );
  });

  it('monta nome com número do pedido de compra', () => {
    expect(buildPdfFilename('pedido-compra', 'PC-20260513-0001', 12)).toBe(
      'pedido-compra-PC-20260513-0001.pdf',
    );
  });

  it('monta nome com número da proposta', () => {
    expect(buildPdfFilename('proposta', 'PROP-20260521-0001', 5)).toBe(
      'proposta-PROP-20260521-0001.pdf',
    );
  });

  it('remove barras e espaços problemáticos', () => {
    expect(buildPdfFilename('proposta', 'PROP/2026-0001', 3)).toBe('proposta-PROP-2026-0001.pdf');
    expect(buildPdfFilename('proposta', 'PROP 2026', 3)).toBe('proposta-PROP2026.pdf');
  });

  it('usa id quando número vazio', () => {
    expect(buildPdfFilename('pedido-venda', '', 42)).toBe('pedido-venda-42.pdf');
    expect(buildPdfFilename('proposta', '   ', 7)).toBe('proposta-7.pdf');
  });
});
