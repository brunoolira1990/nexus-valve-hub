import { describe, expect, it } from 'vitest';
import {
  itemPedidoQuantidadeEditavel,
  labelModoAtendimentoEstoque,
  nfeClienteBloqueado,
  nfeItensComerciaisEditaveis,
  nfeSalvarFormularioBloqueado,
  pedidoItensBloqueados,
} from '@/lib/nfeSaidaUi';

describe('nfeSaidaUi', () => {
  it('bloqueia itens do pedido faturado', () => {
    expect(pedidoItensBloqueados('FATURADO')).toBe(true);
    expect(pedidoItensBloqueados('ABERTO')).toBe(false);
    expect(pedidoItensBloqueados('CANCELADO')).toBe(true);
  });

  it('quantidade editável em pedido aberto sem item faturado', () => {
    expect(itemPedidoQuantidadeEditavel({ status_item: 'PENDENTE', quantidade_faturada: 0 }, 'ABERTO')).toBe(
      true,
    );
    expect(itemPedidoQuantidadeEditavel({ status_item: 'FATURADO', quantidade_faturada: 1 }, 'ABERTO')).toBe(
      false,
    );
    expect(itemPedidoQuantidadeEditavel({ status_item: 'PENDENTE' }, 'FATURADO')).toBe(false);
  });

  it('bloqueia cliente quando há faturamento vinculado', () => {
    expect(nfeClienteBloqueado({ faturamento_pedido_venda_id: 1, pedido_venda_id: 2 })).toBe(true);
    expect(nfeClienteBloqueado({ faturamento_pedido_venda_id: undefined, pedido_venda_id: undefined })).toBe(
      false,
    );
  });

  it('trava itens de NF de faturamento', () => {
    expect(
      nfeItensComerciaisEditaveis({ origem_comercial_travada: true, itens_comerciais_editaveis: false }, 'RASCUNHO'),
    ).toBe(false);
  });

  it('bloqueia salvar formulário para NF finalizada', () => {
    expect(nfeSalvarFormularioBloqueado('AUTORIZADA_INTERNA')).toBe(true);
    expect(nfeSalvarFormularioBloqueado('AUTORIZADA_HOMOLOGACAO')).toBe(true);
    expect(nfeSalvarFormularioBloqueado('RASCUNHO')).toBe(false);
  });

  it('rotula modo de atendimento', () => {
    expect(labelModoAtendimentoEstoque('IMEDIATO')).toBe('Imediato');
    expect(labelModoAtendimentoEstoque('ANTECIPADO')).toBe('Antecipado');
    expect(labelModoAtendimentoEstoque(null)).toBe('—');
  });
});
