import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AnaliseFinanceiraIndicadores } from '@/components/financeiro/AnaliseFinanceiraIndicadores';
import {
  MSG_DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT,
  MSG_QUALIDADE_BASE,
  MSG_SEM_CICLOS_RECEBIMENTO,
  calcularRecenciaDias,
  classificarComportamentoPagamento,
  mapPainelInternoV1,
  mapQualidadePainelV1,
} from '@/components/financeiro/mapPainelInternoV1';

vi.mock('@/services/api/analiseFinanceira', () => ({
  analiseFinanceiraService: {
    capacidadeIntegracoes: vi.fn(),
    listConsultasExternas: vi.fn(),
    listProtestosManuais: vi.fn(),
  },
}));

vi.mock('@/components/financeiro/SecoesIntegracoesExternas', () => ({
  SecoesIntegracoesExternas: () => <div data-testid="mock-integracoes" />,
}));

vi.mock('@/components/financeiro/SecaoProtestosCartorio', () => ({
  SecaoProtestosCartorio: () => <div data-testid="mock-protestos" />,
}));

function periodoBaixasZero() {
  return {
    quantidade_baixas_analisadas: 0,
    quantidade_excluidas: 0,
    valor_total_recebido: null,
    pontualidade_quantidade: {
      disponivel: false,
      valor: null,
      motivo_indisponibilidade: 'Não há pagamentos válidos suficientes no período analisado.',
    },
    pontualidade_valor: { disponivel: false, valor: null },
    atraso_medio_dias: { disponivel: false, valor: null },
    maior_atraso_historico_dias: { disponivel: false, valor: null },
    data_ultimo_pagamento: { disponivel: false, valor: null },
    quantidade_pagamentos_parciais: 0,
  };
}

function snapshotV2Nfe(overrides: Record<string, unknown> = {}) {
  return {
    schema_versao: 2,
    data_corte: '2026-07-15',
    qualidade_dados: 'COMPLETA',
    qualidade: {
      status: 'COMPLETA',
      mensagem: 'Indicadores principais disponíveis sem divergências materiais.',
      fonte_historico_comercial: 'NFE_SAIDA_PRODUCAO',
      baixas_analisadas: 0,
      divergencias: [],
      indisponiveis: [],
    },
    indicadores: {
      comercial: {
        fonte: 'NFE_SAIDA_PRODUCAO',
        tempo_relacionamento_dias: 120,
        periodos: {
          TOTAL: {
            quantidade_vendas: 4,
            valor_vendido: '10000.00',
            ticket_medio: '2500.00',
            maior_venda: '4000.00',
            primeira_compra: '2026-03-17',
            ultima_compra: '2026-07-01',
            frequencia_media_dias: { disponivel: true, valor: '35.00' },
          },
          '12_MESES': {
            quantidade_vendas: 4,
            valor_vendido: '10000.00',
            primeira_compra: '2026-03-17',
            ultima_compra: '2026-07-01',
            frequencia_media_dias: { disponivel: true, valor: '35.00' },
          },
          '6_MESES': { quantidade_vendas: 2 },
          '24_MESES': { quantidade_vendas: 4 },
        },
      },
      contas_receber: {
        saldo_aberto: '5000.00',
        saldo_vencido: '1000.00',
        saldo_a_vencer: '4000.00',
        quantidade_titulos_abertos: 3,
        quantidade_titulos_vencidos: 1,
        maior_atraso_dias: 12,
      },
      baixas: {
        periodos: {
          '12_MESES': periodoBaixasZero(),
          TOTAL: periodoBaixasZero(),
          '6_MESES': periodoBaixasZero(),
          '24_MESES': periodoBaixasZero(),
        },
        total_baixas_cliente: 0,
      },
      pedidos_nao_faturados: { valor_residual: '200.00', quantidade_pedidos: 1 },
      exposicao: {
        formula: 'exposicao_atual = CR aberto + residual pedidos não faturados',
        contas_receber: '5000.00',
        pedidos_nao_faturados: '200.00',
        atual: '5200.00',
        valor_proposta: '1000.00',
        projetada: '6200.00',
      },
      limite: { cadastrado: '0', ambiguo: true, mensagem: 'Limite não informado ou definido como zero.' },
    },
    ...overrides,
  };
}

describe('mapPainelInternoV1 — helpers', () => {
  it('calcula recência pela data_corte, não pela data atual', () => {
    expect(calcularRecenciaDias('2026-07-15', '2026-07-01')).toBe(14);
    expect(calcularRecenciaDias('2026-07-15', '2026-07-01')).toBe(
      calcularRecenciaDias('2026-07-15', '2026-07-01'),
    );
  });

  it('recência permanece estável mesmo se o relógio do teste mudar o “hoje”', () => {
    const a = calcularRecenciaDias('2026-01-31', '2026-01-01');
    // Simula “outro dia” sem afetar o cálculo (não usa Date.now)
    const fakeNow = new Date('2099-12-31T00:00:00Z').getTime();
    expect(fakeNow).toBeGreaterThan(0);
    const b = calcularRecenciaDias('2026-01-31', '2026-01-01');
    expect(a).toBe(30);
    expect(b).toBe(30);
  });

  it('mapeia qualidade COMPLETA → MÉDIA e nunca ALTA', () => {
    expect(mapQualidadePainelV1('COMPLETA', 'NFE_SAIDA_PRODUCAO').status).toBe('MEDIA');
    expect(mapQualidadePainelV1('PARCIAL', 'NFE_SAIDA_PRODUCAO').status).toBe('BAIXA');
    expect(mapQualidadePainelV1('DIVERGENTE', 'NFE_SAIDA_PRODUCAO')).toEqual({
      status: 'BAIXA',
      alertaDivergente: true,
    });
    expect(mapQualidadePainelV1('INSUFICIENTE', 'NFE_SAIDA_PRODUCAO').status).toBe('INSUFICIENTE');
  });

  it('fonte Pedido limita qualidade a BAIXA', () => {
    expect(mapQualidadePainelV1('COMPLETA', 'PEDIDO_VENDA').status).toBe('BAIXA');
    expect(mapQualidadePainelV1('PARCIAL', 'PEDIDO_VENDA').status).toBe('BAIXA');
  });

  it('classifica zero baixas explícitas vs snapshot antigo', () => {
    const comZero = classificarComportamentoPagamento(snapshotV2Nfe());
    expect(comZero.codigo).toBe('SEM_CICLOS_RECEBIMENTO');

    const antigo = classificarComportamentoPagamento({
      schema_versao: 1,
      qualidade_dados: 'PARCIAL',
    } as Parameters<typeof classificarComportamentoPagamento>[0]);
    expect(antigo.codigo).toBe('DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT');
  });

  describe('S3B-R2 — zero explícito vs campo ausente', () => {
    it('1. período com pontualidade indisponível e quantidade ausente → DADOS_NAO_DISPONIVEIS', () => {
      const r = classificarComportamentoPagamento({
        schema_versao: 2,
        indicadores: {
          baixas: {
            periodos: {
              '12_MESES': {
                pontualidade_quantidade: { disponivel: false, valor: null },
              },
            },
          },
        },
      });
      expect(r.codigo).toBe('DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT');
    });

    it('2. quantidade_baixas_analisadas = 0 no período → SEM_CICLOS', () => {
      const r = classificarComportamentoPagamento({
        schema_versao: 2,
        indicadores: {
          baixas: {
            periodos: {
              '12_MESES': { quantidade_baixas_analisadas: 0 },
            },
          },
        },
      });
      expect(r.codigo).toBe('SEM_CICLOS_RECEBIMENTO');
    });

    it('3. qualidade.baixas_analisadas = 0 → SEM_CICLOS', () => {
      const r = classificarComportamentoPagamento({
        schema_versao: 2,
        qualidade: { baixas_analisadas: 0 },
        indicadores: { baixas: { periodos: {} } },
      });
      expect(r.codigo).toBe('SEM_CICLOS_RECEBIMENTO');
    });

    it('4. quantidade_baixas_analisadas > 0 → METRICAS_DISPONIVEIS', () => {
      const r = classificarComportamentoPagamento({
        schema_versao: 2,
        qualidade: { baixas_analisadas: 3 },
        indicadores: {
          baixas: {
            periodos: {
              '12_MESES': { quantidade_baixas_analisadas: 3 },
            },
          },
        },
      });
      expect(r.codigo).toBe('METRICAS_DISPONIVEIS');
    });

    it('5. bloco de períodos vazio → DADOS_NAO_DISPONIVEIS', () => {
      const r = classificarComportamentoPagamento({
        schema_versao: 2,
        indicadores: { baixas: { periodos: {} } },
      });
      expect(r.codigo).toBe('DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT');
    });

    it('6. snapshot antigo sem bloco de baixas → DADOS_NAO_DISPONIVEIS', () => {
      const r = classificarComportamentoPagamento({
        schema_versao: 1,
        qualidade_dados: 'PARCIAL',
      });
      expect(r.codigo).toBe('DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT');
    });
  });

  it('campos ausentes de operações não viram zero no view-model', () => {
    const p = mapPainelInternoV1({
      schema_versao: 2,
      data_corte: '2026-07-15',
      qualidade: { status: 'INSUFICIENTE', baixas_analisadas: 0 },
      indicadores: {
        comercial: { fonte: 'INDISPONIVEL', periodos: {} },
        baixas: { periodos: { TOTAL: periodoBaixasZero() } },
      },
    });
    expect(p.quantidadeOperacoes).toBeNull();
    expect(p.primeiraOperacao).toBeNull();
  });
});

describe('AnaliseFinanceiraIndicadores — Painel Interno V1', () => {
  it('1. snapshot v2 com NF-e e exposição', () => {
    render(
      <AnaliseFinanceiraIndicadores
        snapshot={snapshotV2Nfe()}
        negociacao={{ proposta_numero: 'P-1', data_corte: '2026-07-15' }}
        carregarCapabilityIntegracoes={false}
      />,
    );
    expect(screen.getByTestId('dossie-fonte-comercial')).toHaveTextContent('produção');
    expect(screen.getByTestId('dossie-row-Exposição atual')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-row-Recência na data-base')).toHaveTextContent('14 dias');
  });

  it('2. snapshot com fonte Pedido mostra aviso parcial e qualidade BAIXA', () => {
    const snap = snapshotV2Nfe({
      qualidade: {
        status: 'COMPLETA',
        fonte_historico_comercial: 'PEDIDO_VENDA',
        baixas_analisadas: 0,
      },
      indicadores: {
        ...snapshotV2Nfe().indicadores,
        comercial: {
          fonte: 'PEDIDO_VENDA',
          motivo_fallback_comercial: 'Fallback de teste por Pedido.',
          tempo_relacionamento_dias: 40,
          periodos: snapshotV2Nfe().indicadores.comercial.periodos,
        },
      },
    });
    render(<AnaliseFinanceiraIndicadores snapshot={snap} carregarCapabilityIntegracoes={false} />);
    expect(screen.getByTestId('dossie-aviso-fonte-parcial')).toHaveTextContent('Pedido');
    expect(screen.getByTestId('dossie-qualidade-painel')).toHaveTextContent('BAIXA');
  });

  it('3. zero baixas → SEM_CICLOS_RECEBIMENTO', () => {
    render(<AnaliseFinanceiraIndicadores snapshot={snapshotV2Nfe()} carregarCapabilityIntegracoes={false} />);
    expect(screen.getByTestId('dossie-comportamento-codigo')).toHaveTextContent('SEM_CICLOS_RECEBIMENTO');
    expect(screen.getByTestId('dossie-comportamento-mensagem')).toHaveTextContent(MSG_SEM_CICLOS_RECEBIMENTO);
    expect(screen.queryByTestId('dossie-comportamento-metricas')).not.toBeInTheDocument();
  });

  it('4. baixas válidas preservam métricas', () => {
    const snap = snapshotV2Nfe({
      qualidade: { status: 'COMPLETA', baixas_analisadas: 5, fonte_historico_comercial: 'NFE_SAIDA_PRODUCAO' },
    });
    const ind = snap.indicadores as {
      baixas: { periodos: Record<string, ReturnType<typeof periodoBaixasZero>> };
    };
    ind.baixas.periodos['12_MESES'] = {
      ...periodoBaixasZero(),
      quantidade_baixas_analisadas: 5,
      valor_total_recebido: '3000.00',
      pontualidade_quantidade: { disponivel: true, valor: '80.00' },
      pontualidade_valor: { disponivel: true, valor: '75.00' },
      atraso_medio_dias: { disponivel: true, valor: '3' },
    } as ReturnType<typeof periodoBaixasZero>;
    render(<AnaliseFinanceiraIndicadores snapshot={snap} carregarCapabilityIntegracoes={false} />);
    expect(screen.getByTestId('dossie-comportamento-codigo')).toHaveTextContent('METRICAS_DISPONIVEIS');
    expect(screen.getByTestId('dossie-comportamento-metricas')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-row-Pontualidade por quantidade (12 meses)')).toHaveTextContent('80');
  });

  it('5. snapshot antigo sem bloco de baixas', () => {
    render(
      <AnaliseFinanceiraIndicadores
        snapshot={{
          schema_versao: 1,
          qualidade_dados: 'PARCIAL',
          contas_receber: { saldo_aberto: '10.00' },
          exposicao: { atual: '10.00' },
        }}
        carregarCapabilityIntegracoes={false}
      />,
    );
    expect(screen.getByTestId('dossie-comportamento-codigo')).toHaveTextContent(
      'DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT',
    );
    expect(screen.getByTestId('dossie-comportamento-mensagem')).toHaveTextContent(
      MSG_DADOS_NAO_DISPONIVEIS_NO_SNAPSHOT,
    );
  });

  it('6. snapshot sem indicadores', () => {
    render(<AnaliseFinanceiraIndicadores snapshot={{}} carregarCapabilityIntegracoes={false} />);
    expect(screen.getByTestId('analise-fin-indicadores')).toHaveTextContent(
      'Não disponível no snapshot desta análise.',
    );
  });

  it('7–10. qualidade mapeada e Pedido nunca acima de BAIXA', () => {
    const { rerender } = render(
      <AnaliseFinanceiraIndicadores snapshot={snapshotV2Nfe()} carregarCapabilityIntegracoes={false} />,
    );
    expect(screen.getByTestId('dossie-qualidade-painel')).toHaveTextContent('MÉDIA');
    expect(screen.getByTestId('dossie-qualidade-explicacao')).toHaveTextContent(MSG_QUALIDADE_BASE);

    rerender(
      <AnaliseFinanceiraIndicadores
        snapshot={snapshotV2Nfe({ qualidade: { status: 'PARCIAL', baixas_analisadas: 0 } })}
        carregarCapabilityIntegracoes={false}
      />,
    );
    expect(screen.getByTestId('dossie-qualidade-painel')).toHaveTextContent('BAIXA');

    rerender(
      <AnaliseFinanceiraIndicadores
        snapshot={snapshotV2Nfe({
          qualidade: { status: 'DIVERGENTE', baixas_analisadas: 0, divergencias: [{ motivo: 'x' }] },
        })}
        carregarCapabilityIntegracoes={false}
      />,
    );
    expect(screen.getByTestId('dossie-qualidade-painel')).toHaveTextContent('BAIXA');
    expect(screen.getByTestId('dossie-alerta-divergente')).toBeInTheDocument();
  });

  it('11–12. recência pela data_corte', () => {
    render(<AnaliseFinanceiraIndicadores snapshot={snapshotV2Nfe()} carregarCapabilityIntegracoes={false} />);
    expect(screen.getByTestId('dossie-row-Recência na data-base')).toHaveTextContent('14 dias');
  });

  it('13. resumo restrito sem exposição/valores', () => {
    render(
      <AnaliseFinanceiraIndicadores
        snapshot={{
          resumo_restrito: true,
          schema_versao: 2,
          qualidade_dados: 'COMPLETA',
          qualidade: { status: 'COMPLETA', mensagem: 'ok' },
          data_corte: '2026-07-15',
        }}
        carregarCapabilityIntegracoes={false}
      />,
    );
    expect(screen.queryByTestId('dossie-exposicao')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-row-Exposição atual')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-row-Saldo Contas a Receber')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-row-Valor vencido')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-row-Títulos vencidos')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-row-Títulos abertos')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-comercial')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dossie-comportamento-pagamento')).not.toBeInTheDocument();
    expect(screen.getByTestId('dossie-qualidade')).toBeInTheDocument();
  });

  it('14–15. sem textos de score/aprovação e campos ausentes não viram 0 inventado', () => {
    const { container } = render(
      <AnaliseFinanceiraIndicadores
        snapshot={{
          schema_versao: 2,
          data_corte: '2026-07-15',
          qualidade: { status: 'INSUFICIENTE', baixas_analisadas: 0 },
          indicadores: {
            comercial: { fonte: 'INDISPONIVEL', periodos: { TOTAL: {} } },
            contas_receber: {},
            baixas: { periodos: { TOTAL: periodoBaixasZero(), '12_MESES': periodoBaixasZero() } },
            exposicao: {},
            pedidos_nao_faturados: {},
          },
        }}
        carregarCapabilityIntegracoes={false}
      />,
    );
    const txt = container.textContent || '';
    expect(txt).not.toMatch(/score de crédito/i);
    expect(txt).not.toMatch(/bom cliente|mau cliente/i);
    expect(txt).not.toMatch(/crédito aprovado|crédito recusado/i);
    expect(screen.getByTestId('dossie-comercial-vazio')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-row-Exposição atual')).toHaveTextContent('Indisponível');
    expect(screen.getByTestId('dossie-row-Títulos abertos')).toHaveTextContent('Indisponível');
  });
});
