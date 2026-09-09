import { describe, expect, it } from 'vitest';
import { percentualSaidaTotal } from '@/lib/propostaPricing';
import { sanitizeItemPropostaForApi, sanitizePropostaRestForApi } from '@/lib/propostaApiPayload';
import type { ItemProposta } from '@/types';

describe('sanitizeItemPropostaForApi', () => {
  it('remove campos somente leitura e UI (regra_fiscal_origem, produto_nome)', () => {
    const item = {
      id: 999,
      produto_id: 1,
      produto_nome: 'Parafuso',
      quantidade: '2.00',
      icms_saida_percentual: '18.00',
      pis_saida_percentual: '1.65',
      cofins_saida_percentual: '7.60',
      regra_fiscal_origem: 'CENARIO_SAIDA',
      origem_regra_fiscal_saida: 'CENARIO_SAIDA',
      ipi_entrada_valor: 10,
      custo_carregado: 100,
      item_avulso: false,
    } as unknown as ItemProposta;

    const payload = sanitizeItemPropostaForApi(item);
    expect(payload).not.toHaveProperty('regra_fiscal_origem');
    expect(payload).not.toHaveProperty('produto_nome');
    expect(payload).not.toHaveProperty('id');
    expect(payload.icms_saida_percentual).toBe(18);
    expect(payload.pis_saida_percentual).toBe(1.65);
  });
});

describe('sanitizePropostaRestForApi', () => {
  it('preserva o frete de cabeçalho e remove campos somente leitura', () => {
    const payload = sanitizePropostaRestForApi({
      valor_frete: 12.34,
      cliente_nome: 'Somente leitura',
      itens: [],
    });
    expect(payload.valor_frete).toBe(12.34);
    expect(payload).not.toHaveProperty('cliente_nome');
    expect(payload).not.toHaveProperty('itens');
  });
});

describe('percentualSaidaTotal', () => {
  it('soma alíquotas quando API devolve strings decimais', () => {
    const pct = percentualSaidaTotal({
      icms_saida_percentual: '18.00',
      pis_saida_percentual: '1.65',
      cofins_saida_percentual: '7.60',
    } as ItemProposta);
    expect(Number.isFinite(pct)).toBe(true);
    expect(pct).toBeGreaterThan(0);
  });
});
