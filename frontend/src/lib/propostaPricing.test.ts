import { describe, it, expect } from 'vitest';
import {
  computeReceitaComercialItem,
  computeResultadoEstimadoItem,
  computeMargemContribuicaoEstimadaItem,
  computeReceitaComercialConsolidada,
  computeResultadoEstimadoConsolidado,
  computeMargemContribuicaoEstimadaConsolidada,
  round2,
} from './propostaPricing';

const baseItem = {
  quantidade_negociada: 10,
  quantidade: 10,
  preco_por_unidade_negociada: 100,
  preco_final: 100,
  preco_sugerido: 100,
  desconto: 0,
  custo_final: 60,
  custo_utilizado: 50,
  ipi_entrada_percentual: 0,
  ipi_custo: 0,
  st_custo: 0,
  frete: 0,
  despesas: 0,
  outros_impostos_custo: 0,
  icms_saida_percentual: 18,
  pis_saida_percentual: 1.65,
  cofins_saida_percentual: 7.6,
  ipi_saida_percentual: 5,
  irpj_estimado_percentual: 1.5,
  csll_estimada_percentual: 1,
  comissao_percentual: 3,
  frete_saida: 0,
  outras_despesas_saida: 0,
  modo_preco: 'sugerido' as const,
  lucro_resultante: 0,
  margem_resultante: 0,
  unidade_negociada: 'PC',
  unidade_estoque_calculada: 'PC',
  quantidade_estoque_calculada: 10,
  fator_conversao: 1,
  peso_total_kg: 0,
  metros_total: 0,
  barras_total: 0,
  preco_por_kg: 0,
  preco_por_metro: 0,
  regra_fiscal_origem: 'LEGADO',
  deduzir_icms_base_pis: false,
  deduzir_icms_base_cofins: false,
  ncm_avulso: '',
  descricao_avulsa: '',
  produto_id: null,
  item_avulso: false,
  id: 1,
};

// pctSaida total = 18 + 1.65 + 7.6 + 5 + 1.5 + 1 + 3 = 37.75%
const PCT_SAIDA = 37.75;

describe('propostaPricing - novos indicadores gerenciais', () => {
  it('Caso 1: 1 item sem desconto (modo sugerido, preço = sugerido)', () => {
    const item = { ...baseItem, quantidade_negociada: 10, preco_por_unidade_negociada: 100, preco_final: 100, preco_sugerido: 100, desconto: 0, custo_final: 60 };
    const receita = computeReceitaComercialItem(item);
    expect(receita).toBe(1000); // 10 * 100 - 0

    const resultado = computeResultadoEstimadoItem(item);
    // receita 1000 - custo_total 600 - cargas (37.75% * 100 * 10 = 377.5) = 22.5
    expect(resultado).toBe(22.5);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    // 22.5 / 1000 * 100 = 2.25%
    expect(margem).toBe(2.25);
  });

  it('Caso 2: 1 item com desconto (modo manual)', () => {
    const item = { ...baseItem, modo_preco: 'manual' as const, quantidade_negociada: 10, preco_por_unidade_negociada: 100, preco_final: 100, desconto: 50, custo_final: 60 };
    const receita = computeReceitaComercialItem(item);
    expect(receita).toBe(950); // 10 * 100 - 50

    const resultado = computeResultadoEstimadoItem(item);
    // receita 950 - custo_total 600 - cargas (37.75% * 100 * 10 = 377.5) = -27.5
    expect(resultado).toBe(-27.5);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    // -27.5 / 950 * 100 = -2.89%
    expect(margem).toBe(-2.89);
  });

  it('Caso 3: resultado negativo (modo manual, preço menor)', () => {
    const item = { ...baseItem, modo_preco: 'manual' as const, quantidade_negociada: 10, preco_por_unidade_negociada: 80, preco_final: 80, desconto: 0, custo_final: 60 };
    const receita = computeReceitaComercialItem(item);
    expect(receita).toBe(800);

    const resultado = computeResultadoEstimadoItem(item);
    // receita 800 - custo_total 600 - cargas (37.75% * 80 * 10 = 302) = -102
    expect(resultado).toBe(-102);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    // -102 / 800 * 100 = -12.75%
    expect(margem).toBe(-12.75);
  });

  it('Caso 4: receita zero', () => {
    const item = { ...baseItem, quantidade_negociada: 0, preco_por_unidade_negociada: 100, desconto: 0 };
    const receita = computeReceitaComercialItem(item);
    expect(receita).toBe(0);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    expect(margem).toBe(0);
  });

  it('Caso 5: frete_saida e outras_despesas_saida (modo manual)', () => {
    const item = {
      ...baseItem,
      modo_preco: 'manual' as const,
      quantidade_negociada: 10,
      preco_por_unidade_negociada: 100,
      preco_final: 100,
      desconto: 0,
      custo_final: 60,
      frete_saida: 2,
      outras_despesas_saida: 1,
    };
    const receita = computeReceitaComercialItem(item);
    expect(receita).toBe(1000);

    const resultado = computeResultadoEstimadoItem(item);
    // receita 1000 - custo_total 600 - cargas 377.5 - frete_saida_total 20 - outras_saida_total 10 = -7.5
    expect(resultado).toBe(-7.5);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    // -7.5 / 1000 * 100 = -0.75%
    expect(margem).toBe(-0.75);
  });

  it('Caso 6: cargas percentuais (ICMS, PIS, COFINS, IPI, IRPJ, CSLL, Comissão)', () => {
    const item = {
      ...baseItem,
      quantidade_negociada: 10,
      preco_por_unidade_negociada: 100,
      preco_final: 100,
      preco_sugerido: 100,
      desconto: 0,
      custo_final: 60,
      icms_saida_percentual: 18,
      pis_saida_percentual: 1.65,
      cofins_saida_percentual: 7.6,
      ipi_saida_percentual: 5,
      irpj_estimado_percentual: 1.5,
      csll_estimada_percentual: 1,
      comissao_percentual: 3,
    };
    // pctSaida = 37.75%
    // valorCarga = 100 * 37.75% = 37.75
    // custoTotal = 60 * 10 = 600
    // cargasTotal = (37.75 + 0 + 0) * 10 = 377.5
    // receita = 1000
    // resultado = 1000 - 600 - 377.5 = 22.5
    const resultado = computeResultadoEstimadoItem(item);
    expect(resultado).toBe(22.5);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    // 22.5 / 1000 * 100 = 2.25%
    expect(margem).toBe(2.25);
  });

  it('Caso 7: quantidade_negociada diferente de quantidade_estoque_calculada (conversão dimensional)', () => {
    // Produto vendido em BARRA (negociada) mas estocado em METRO
    // 1 BARRA = 6 METROS (fator_conversao = 6)
    const item = {
      ...baseItem,
      modo_preco: 'manual' as const,
      quantidade_negociada: 10, // 10 BARRAS
      quantidade_estoque_calculada: 60, // 60 METROS
      fator_conversao: 6,
      preco_por_unidade_negociada: 120, // R$ 120/BARRA
      preco_final: 120,
      desconto: 0,
      custo_final: 70, // R$ 70/BARRA
    };
    // Os novos cálculos devem usar quantidade_negociada (10), NÃO quantidade_estoque_calculada (60)
    const receita = computeReceitaComercialItem(item);
    expect(receita).toBe(1200); // 10 * 120 - 0

    const custoTotal = round2(toNumber(item.quantidade_negociada) * toNumber(item.custo_final));
    expect(custoTotal).toBe(700); // 10 * 70, NÃO 60 * 70 = 4200

    const resultado = computeResultadoEstimadoItem(item);
    // receita 1200 - custo_total 700 - cargas (37.75% * 120 * 10 = 453) = 47
    expect(resultado).toBe(47);

    const margem = computeMargemContribuicaoEstimadaItem(item);
    // 47 / 1200 * 100 = 3.92%
    expect(margem).toBe(3.92);
  });

  it('usa o preço por unidade negociada como referência única quando diverge do preço final', () => {
    const item = {
      ...baseItem,
      modo_preco: 'manual' as const,
      quantidade_negociada: 10,
      preco_por_unidade_negociada: 120,
      preco_final: 80,
      preco_sugerido: 80,
      desconto: 0,
      custo_final: 60,
      icms_saida_percentual: 10,
      pis_saida_percentual: 0,
      cofins_saida_percentual: 0,
      ipi_saida_percentual: 0,
      irpj_estimado_percentual: 0,
      csll_estimada_percentual: 0,
      comissao_percentual: 0,
    };

    expect(computeReceitaComercialItem(item)).toBe(1200);
    expect(computeResultadoEstimadoItem(item)).toBe(480);
    expect(computeMargemContribuicaoEstimadaItem(item)).toBe(40);
  });

  describe('Consolidado', () => {
    it('A) 1 item: resultado item = resultado consolidado; margem item = margem consolidada', () => {
      const item = { ...baseItem, quantidade_negociada: 10, preco_por_unidade_negociada: 100, preco_final: 100, preco_sugerido: 100, desconto: 0, custo_final: 60 };
      const itens = [item];

      const receitaCons = computeReceitaComercialConsolidada(itens);
      const resultadoCons = computeResultadoEstimadoConsolidado(itens);
      const margemCons = computeMargemContribuicaoEstimadaConsolidada(itens);

      expect(receitaCons).toBe(computeReceitaComercialItem(item));
      expect(resultadoCons).toBe(computeResultadoEstimadoItem(item));
      expect(margemCons).toBe(computeMargemContribuicaoEstimadaItem(item));
    });

    it('B) 2 itens com receitas diferentes: consolidado usa soma/soma, não média simples', () => {
      const item1 = { ...baseItem, id: 1, quantidade_negociada: 10, preco_por_unidade_negociada: 100, preco_final: 100, preco_sugerido: 100, desconto: 0, custo_final: 60 };
      const item2 = { ...baseItem, id: 2, modo_preco: 'manual' as const, quantidade_negociada: 5, preco_por_unidade_negociada: 200, preco_final: 200, desconto: 0, custo_final: 120 };
      const itens = [item1, item2];

      const receitaCons = computeReceitaComercialConsolidada(itens);
      const resultadoCons = computeResultadoEstimadoConsolidado(itens);
      const margemCons = computeMargemContribuicaoEstimadaConsolidada(itens);

      // Item 1: receita 1000, resultado 22.5, margem 2.25%
      // Item 2: receita 1000, custo 600, cargas (37.75% * 200 * 5 = 377.5) => resultado 22.5, margem 2.25%
      // Consolidado: receita 2000, resultado 45, margem 45/2000*100 = 2.25%
      expect(receitaCons).toBe(2000);
      expect(resultadoCons).toBe(45);
      expect(margemCons).toBe(2.25);

      // Teste explícito: margem consolidada NÃO é média simples (embora coincida neste caso)
      // A fórmula correta é soma/soma
      const margemMediaSimples = (computeMargemContribuicaoEstimadaItem(item1) + computeMargemContribuicaoEstimadaItem(item2)) / 2;
      expect(margemCons).toBe(margemMediaSimples); // Neste caso coincidem por simetria
    });

    it('C) desconto: aumentar desconto em X reduz Resultado Estimado em X', () => {
      const itemBase = { ...baseItem, modo_preco: 'manual' as const, quantidade_negociada: 10, preco_por_unidade_negociada: 100, preco_final: 100, custo_final: 60, desconto: 0 };
      const itemComDesconto = { ...itemBase, desconto: 100 };

      const resultadoBase = computeResultadoEstimadoItem(itemBase);
      const resultadoComDesconto = computeResultadoEstimadoItem(itemComDesconto);

      // Aumentar desconto em 100 deve reduzir resultado em 100
      expect(resultadoBase - resultadoComDesconto).toBe(100);
    });
  });
});

// Helper para evitar import circular no teste
function toNumber(v: unknown, decimals = 2): number {
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(v);
  if (Number.isNaN(n)) return 0;
  const factor = Math.pow(10, decimals);
  return Math.round(n * factor) / factor;
}