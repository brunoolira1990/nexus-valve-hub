import { describe, expect, it } from 'vitest';
import { normalizePedidoVendaRow, resolvePedidoVendaId } from './pedidoVendaId';

describe('resolvePedidoVendaId', () => {
  it('usa id numérico', () => {
    expect(resolvePedidoVendaId({ id: 12 })).toBe(12);
  });

  it('usa pk quando id ausente', () => {
    expect(resolvePedidoVendaId({ pk: 7 })).toBe(7);
  });

  it('rejeita numero do pedido como id', () => {
    expect(resolvePedidoVendaId({ id: 'PV-20260521-0001' })).toBeNull();
  });

  it('rejeita id inválido', () => {
    expect(resolvePedidoVendaId({ id: undefined })).toBeNull();
    expect(resolvePedidoVendaId({ id: 0 })).toBeNull();
  });
});

describe('normalizePedidoVendaRow', () => {
  it('preenche id a partir de pk', () => {
    const row = normalizePedidoVendaRow({ pk: 3, numero: 'PV-1' });
    expect(row.id).toBe(3);
  });
});
