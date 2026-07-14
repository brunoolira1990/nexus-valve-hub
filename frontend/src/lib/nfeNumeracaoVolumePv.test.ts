import { describe, expect, it } from 'vitest';
import {
  MSG_NUMERACAO_PADRAO_SUGERIDO,
  MSG_NUMERACAO_SUGERIDA_DO_PV,
  compactarNumeroPedidoVenda,
  textoAjudaNumeracaoVolumes,
} from './nfeNumeracaoVolumePv';

describe('compactarNumeroPedidoVenda', () => {
  it('compacta o formato aprovado', () => {
    expect(compactarNumeroPedidoVenda('PV-20260714-0042')).toBe('260714-0042');
    expect(compactarNumeroPedidoVenda('PV-20260101-0001')).toBe('260101-0001');
  });

  it('valida data e bissexto', () => {
    expect(compactarNumeroPedidoVenda('PV-20240229-0001')).toBe('240229-0001');
    expect(compactarNumeroPedidoVenda('PV-20260229-0001')).toBeNull();
    expect(compactarNumeroPedidoVenda('PV-20261301-0001')).toBeNull();
  });

  it('rejeita legados e incompletos', () => {
    expect(compactarNumeroPedidoVenda('4368')).toBeNull();
    expect(compactarNumeroPedidoVenda('PV-20260714-42')).toBeNull();
    expect(compactarNumeroPedidoVenda(null)).toBeNull();
    expect(compactarNumeroPedidoVenda('')).toBeNull();
  });
});

describe('textoAjudaNumeracaoVolumes', () => {
  it('afirma origem somente quando o valor atual é o compacto do PV', () => {
    expect(textoAjudaNumeracaoVolumes('260714-0042', 'PV-20260714-0042')).toBe(
      MSG_NUMERACAO_SUGERIDA_DO_PV,
    );
  });

  it('usa mensagem genérica se o valor foi alterado ou PV legado', () => {
    expect(textoAjudaNumeracaoVolumes('VOL-MANUAL', 'PV-20260714-0042')).toBe(
      MSG_NUMERACAO_PADRAO_SUGERIDO,
    );
    expect(textoAjudaNumeracaoVolumes('', '4368')).toBe(MSG_NUMERACAO_PADRAO_SUGERIDO);
    expect(textoAjudaNumeracaoVolumes('260714-0042', '4368')).toBe(MSG_NUMERACAO_PADRAO_SUGERIDO);
  });
});
