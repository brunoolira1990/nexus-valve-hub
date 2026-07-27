import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AnalisesFinanceirasPage from '@/pages/financeiro/AnalisesFinanceirasPage';
import {
  AnaliseFinanceiraIndicadores,
  AVISO_QUALIDADE_PARCIAL,
  MSG_SNAPSHOT_ANTIGO,
} from '@/components/financeiro/AnaliseFinanceiraIndicadores';
import { PropostaAnaliseFinanceiraPanel } from '@/components/comercial/PropostaAnaliseFinanceiraPanel';
import { analiseFinanceiraService } from '@/services/api/analiseFinanceira';
import { apiErrorMessage, PERMISSION_DENIED_MESSAGE } from '@/services/api/config';

vi.mock('@/services/api/analiseFinanceira', () => ({
  analiseFinanceiraService: {
    situacaoProposta: vi.fn(),
    solicitar: vi.fn(),
    list: vi.fn(),
    getById: vi.fn(),
    iniciar: vi.fn(),
    aprovar: vi.fn(),
    aprovarComAjuste: vi.fn(),
    devolver: vi.fn(),
    naoAprovar: vi.fn(),
    capacidadeIntegracoes: vi.fn(),
    listConsultasExternas: vi.fn(),
  },
}));

const capacidadeDesabilitada = {
  cadastral: {
    configurado: false,
    disponivel: false,
    provider: null,
    produto: null,
    permite_consulta: false,
    motivo: 'PROVIDER_NAO_CONFIGURADO',
  },
  buro: {
    configurado: false,
    disponivel: false,
    provider: null,
    produto: null,
    permite_consulta: false,
    motivo: 'BURO_NAO_CONTRATADO',
  },
  decisao_financeira: 'MANUAL' as const,
};

const snapshotV2 = {
  schema_versao: 2,
  data_corte: '2026-07-24',
  qualidade_dados: 'PARCIAL',
  dados_indisponiveis: ['pontualidade_12_meses'],
  qualidade: {
    status: 'PARCIAL',
    mensagem: AVISO_QUALIDADE_PARCIAL,
    indisponiveis: [{ indicador: 'pontualidade_12_meses', motivo: 'Não há pagamentos válidos suficientes no período analisado.' }],
    fonte_historico_comercial: 'NFE_SAIDA_PRODUCAO',
    divergencias: [],
    pedidos_analisados: 2,
    titulos_analisados: 1,
    baixas_analisadas: 0,
  },
  indicadores: {
    comercial: {
      fonte: 'NFE_SAIDA_PRODUCAO',
      fonte_historico_comercial: 'NFE_SAIDA_PRODUCAO',
      ambiente_fiscal_considerado: 'PRODUCAO',
      documentos_homologacao_ignorados: 0,
      motivo_fallback_comercial: null,
      quantidade_pedidos_cancelados: 0,
      tempo_relacionamento_dias: 100,
      periodos: {
        '6_MESES': {
          quantidade_vendas: 1,
          valor_vendido: '500.00',
          ticket_medio: '500.00',
          maior_venda: '500.00',
          primeira_compra: '2026-06-01',
          ultima_compra: '2026-06-01',
          frequencia_media_dias: { disponivel: false, valor: null, motivo_indisponibilidade: 'uma compra' },
        },
        '12_MESES': {
          quantidade_vendas: 2,
          valor_vendido: '1500.00',
          ticket_medio: '750.00',
          maior_venda: '1000.00',
          primeira_compra: '2026-01-01',
          ultima_compra: '2026-06-01',
          frequencia_media_dias: { disponivel: true, valor: '151.00' },
        },
        '24_MESES': {
          quantidade_vendas: 2,
          valor_vendido: '1500.00',
          ticket_medio: '750.00',
          maior_venda: '1000.00',
          primeira_compra: '2026-01-01',
          ultima_compra: '2026-06-01',
          frequencia_media_dias: { disponivel: true, valor: '151.00' },
        },
        TOTAL: {
          quantidade_vendas: 2,
          valor_vendido: '1500.00',
          ticket_medio: '750.00',
          maior_venda: '1000.00',
          primeira_compra: '2026-01-01',
          ultima_compra: '2026-06-01',
          frequencia_media_dias: { disponivel: true, valor: '151.00' },
        },
      },
    },
    contas_receber: {
      saldo_aberto: '200.00',
      saldo_a_vencer: '120.00',
      saldo_vencido: '80.00',
      quantidade_titulos_vencidos: 1,
      maior_atraso_dias: 10,
    },
    baixas: {
      periodos: {
        '12_MESES': {
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
        },
      },
    },
    pedidos_nao_faturados: { valor_residual: '50.00', quantidade_pedidos: 1 },
    exposicao: {
      contas_receber: '200.00',
      pedidos_nao_faturados: '50.00',
      atual: '250.00',
      valor_proposta: '200.00',
      projetada: '450.00',
    },
    limite: {
      cadastrado: '100.00',
      ambiguo: false,
      disponivel_antes: { disponivel: true, valor: '-150.00' },
      disponivel_depois: { disponivel: true, valor: '-350.00' },
      excesso_sobre_limite: { disponivel: true, valor: '350.00' },
    },
  },
  contas_receber: {
    disponivel: true,
    saldo_aberto: '200.00',
    saldo_a_vencer: '120.00',
    saldo_vencido: '80.00',
    quantidade_titulos_vencidos: 1,
  },
  exposicao: { atual: '250.00', projetada: '450.00', valor_proposta: '200.00' },
};

describe('AnaliseFinanceiraIndicadores dossiê B1', () => {
  beforeEach(() => {
    vi.mocked(analiseFinanceiraService.capacidadeIntegracoes).mockResolvedValue(capacidadeDesabilitada);
  });

  it('seções A–F e sem JSON bruto', () => {
    const { container } = render(
      <AnaliseFinanceiraIndicadores
        snapshot={snapshotV2}
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        negociacao={{
          proposta_numero: 'P-1',
          cliente_nome: 'Cliente X',
          valor_solicitado: '200.00',
          condicao: '30',
          vendedor: 'Ana',
          solicitada_em: '2026-07-24T12:00:00Z',
          data_corte: '2026-07-24',
        }}
      />,
    );
    expect(screen.getByTestId('dossie-negociacao')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-comercial')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-financeiro')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-exposicao')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-qualidade')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-cadastral-placeholder')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-buro-placeholder')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-recomendacao-placeholder')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-qualidade-status')).toHaveTextContent('PARCIAL');
    expect(screen.getByTestId('analise-fin-indisponiveis')).toHaveTextContent('pontualidade_12_meses');
    expect(container.textContent).not.toMatch(/"schema_versao"/);
    expect(container.textContent).not.toContain('null');
    expect(screen.getByTestId('dossie-fonte-comercial')).toHaveTextContent('NF-e de saída autorizada em produção');
    expect(screen.queryByTestId('dossie-aviso-homologacao')).not.toBeInTheDocument();
  });

  it('fonte PedidoVenda com aviso de homologação ignorada', () => {
    render(
      <AnaliseFinanceiraIndicadores
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        snapshot={{
          ...snapshotV2,
          indicadores: {
            ...snapshotV2.indicadores,
            comercial: {
              ...snapshotV2.indicadores.comercial,
              fonte: 'PEDIDO_VENDA',
              ambiente_fiscal_considerado: 'NAO_APLICAVEL',
              documentos_homologacao_ignorados: 2,
              motivo_fallback_comercial:
                'Documentos fiscais de homologação não foram considerados como vendas reais. O histórico comercial foi calculado pelos Pedidos de Venda.',
            },
          },
        }}
      />,
    );
    expect(screen.getByTestId('dossie-fonte-comercial')).toHaveTextContent('Pedidos de Venda');
    expect(screen.getByTestId('dossie-aviso-homologacao')).toHaveTextContent('homologação');
  });

  it('fonte indisponível', () => {
    render(
      <AnaliseFinanceiraIndicadores
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        snapshot={{
          ...snapshotV2,
          indicadores: {
            ...snapshotV2.indicadores,
            comercial: {
              ...snapshotV2.indicadores.comercial,
              fonte: 'INDISPONIVEL',
              periodos: {
                TOTAL: {
                  quantidade_vendas: 0,
                  valor_vendido: '0.00',
                  ticket_medio: '0.00',
                  maior_venda: '0.00',
                  primeira_compra: null,
                  ultima_compra: null,
                  frequencia_media_dias: { disponivel: false, valor: null },
                },
              },
            },
          },
        }}
      />,
    );
    expect(screen.getByTestId('dossie-fonte-comercial')).toHaveTextContent('Fonte indisponível');
  });

  it('limite negativo e excesso', () => {
    render(<AnaliseFinanceiraIndicadores snapshot={snapshotV2} capacidadeIntegracoes={capacidadeDesabilitada} carregarCapabilityIntegracoes={false} />);
    expect(screen.getByTestId('dossie-exposicao').textContent).toMatch(/-R\$\s*150/);
  });

  it('limite zero ambíguo', () => {
    render(
      <AnaliseFinanceiraIndicadores
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        snapshot={{
          ...snapshotV2,
          indicadores: {
            ...snapshotV2.indicadores,
            limite: {
              cadastrado: '0.00',
              ambiguo: true,
              mensagem: 'Limite não informado ou definido como zero.',
              disponivel_antes: { disponivel: false, valor: null },
              disponivel_depois: { disponivel: false, valor: null },
              excesso_sobre_limite: { disponivel: false, valor: null },
            },
          },
        }}
      />,
    );
    expect(screen.getByTestId('dossie-exposicao').textContent).toMatch(/não informado|Indisponível/i);
  });

  it('qualidade DIVERGENTE', () => {
    render(
      <AnaliseFinanceiraIndicadores
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        snapshot={{
          ...snapshotV2,
          qualidade_dados: 'DIVERGENTE',
          qualidade: {
            ...snapshotV2.qualidade,
            status: 'DIVERGENTE',
            mensagem: 'Divergência detectada.',
            divergencias: [{ motivo: 'CR com residual' }],
          },
        }}
      />,
    );
    expect(screen.getByTestId('dossie-qualidade-status')).toHaveTextContent('DIVERGENTE');
    expect(screen.getByTestId('dossie-divergencias')).toHaveTextContent('CR com residual');
  });

  it('snapshot antigo permanece legível', () => {
    render(
      <AnaliseFinanceiraIndicadores
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        snapshot={{
          qualidade_dados: 'PARCIAL',
          data_corte: '2026-01-01',
          contas_receber: { disponivel: true, saldo_aberto: '10.00', saldo_vencido: '0', saldo_a_vencer: '10.00' },
          exposicao: { atual: '10.00', projetada: '20.00', valor_proposta: '10.00' },
          percentual_pontualidade: { disponivel: false, valor: null, motivo: 'Sem regra' },
          dados_indisponiveis: ['percentual_pontualidade'],
        }}
      />,
    );
    expect(screen.getByTestId('dossie-snapshot-antigo')).toHaveTextContent(MSG_SNAPSHOT_ANTIGO);
    expect(screen.getByTestId('dossie-financeiro')).toBeInTheDocument();
  });

  it('resumo restrito', () => {
    render(
      <AnaliseFinanceiraIndicadores
        capacidadeIntegracoes={capacidadeDesabilitada}
        carregarCapabilityIntegracoes={false}
        snapshot={{ qualidade_dados: 'PARCIAL', resumo_restrito: true, qualidade: { status: 'PARCIAL' } }}
      />,
    );
    expect(screen.queryByTestId('dossie-exposicao')).not.toBeInTheDocument();
    expect(screen.getByTestId('dossie-cadastral-placeholder')).toBeInTheDocument();
  });
});

describe('PropostaAnaliseFinanceiraPanel', () => {
  beforeEach(() => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockReset();
    vi.mocked(analiseFinanceiraService.solicitar).mockReset();
  });

  it('painel sem análise e botão solicitar', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockResolvedValue({
      situacao: {
        avaliacao: {
          exige_liberacao: true,
          a_vista: false,
          valida: false,
          motivo_codigo: 'SEM_APROVACAO',
          motivo: 'Precisa de liberação financeira válida.',
          condicao_atual: {
            texto: '30/60',
            dias: [30, 60],
            quantidade_parcelas: 2,
            modalidade: 'PARCELADO',
            maior_prazo_dias: 60,
          },
          analise_id: null,
        },
        ultima_analise_id: null,
        ultima_analise_status: null,
        analise_ativa_id: null,
        reanalise_necessaria: true,
        permissoes: { pode_solicitar: true, pode_decidir: false, pode_ver_detalhe_financeiro: false },
      },
      ultima: null,
      historico: [],
    });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} enabled />);
    await waitFor(() => expect(analiseFinanceiraService.situacaoProposta).toHaveBeenCalledWith(10));
    expect(screen.getByTestId('analise-fin-solicitar')).toBeInTheDocument();
  });

  it('erro 403 tratado', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockRejectedValue({
      response: { status: 403, data: { detail: 'Sem permissão.' } },
    });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => expect(screen.getByTestId('analise-fin-erro')).toHaveTextContent(PERMISSION_DENIED_MESSAGE));
  });

  it('erro de rede não interpreta como aprovação', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockRejectedValue({ message: 'Network Error' });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => expect(screen.getByTestId('analise-fin-erro')).toBeInTheDocument());
    expect(screen.getByTestId('analise-fin-status')).toHaveTextContent('Não solicitada');
  });
});

describe('AnalisesFinanceirasPage dossiê', () => {
  const baseAnalise = {
    id: 7,
    proposta: 10,
    proposta_numero: 'P-1',
    cliente: 1,
    cliente_nome: 'Cliente X',
    status: 'PENDENTE',
    versao: 1,
    solicitada_em: '2026-07-24T12:00:00Z',
    valor_solicitado: '200.00',
    condicao_solicitada: {
      texto: '30',
      dias: [30],
      quantidade_parcelas: 1,
      modalidade: 'A_PRAZO',
      maior_prazo_dias: 30,
    },
    snapshot_proposta: { vendedor: 'Ana', data_corte: '2026-07-24' },
    snapshot_indicadores: snapshotV2,
    permissoes: { pode_decidir: true, pode_ver_detalhe_financeiro: true },
  };

  beforeEach(() => {
    vi.mocked(analiseFinanceiraService.list).mockReset();
    vi.mocked(analiseFinanceiraService.getById).mockReset();
    vi.mocked(analiseFinanceiraService.aprovar).mockReset();
    vi.mocked(analiseFinanceiraService.capacidadeIntegracoes).mockReset();
    vi.mocked(analiseFinanceiraService.list).mockResolvedValue({ count: 1, results: [baseAnalise] });
    vi.mocked(analiseFinanceiraService.getById).mockResolvedValue(baseAnalise);
    vi.mocked(analiseFinanceiraService.capacidadeIntegracoes).mockResolvedValue(capacidadeDesabilitada);
  });

  it('abre detalhe com dossiê e ações', async () => {
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('analise-fin-abrir-7'));
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => expect(screen.getByTestId('dossie-negociacao')).toBeInTheDocument());
    expect(screen.getByTestId('analise-fin-acoes')).toBeInTheDocument();
    expect(screen.queryByText(/"exposicao"/)).not.toBeInTheDocument();
  });

  it('aprovar como solicitado permanece', async () => {
    vi.mocked(analiseFinanceiraService.aprovar).mockResolvedValue({ ...baseAnalise, status: 'APROVADA' });
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('analise-fin-abrir-7'));
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => screen.getByTestId('analise-fin-aprovar'));
    fireEvent.click(screen.getByTestId('analise-fin-aprovar'));
    await waitFor(() => expect(analiseFinanceiraService.aprovar).toHaveBeenCalledWith(7));
  });
});

describe('mensagem de conversão bloqueada', () => {
  it('apiErrorMessage usa detail do guard', () => {
    const msg = apiErrorMessage({
      response: {
        status: 400,
        data: {
          code: 'SEM_APROVACAO',
          detail: 'Esta proposta possui pagamento futuro e precisa de liberação financeira.',
        },
      },
    });
    expect(msg).toContain('liberação financeira');
  });
});
