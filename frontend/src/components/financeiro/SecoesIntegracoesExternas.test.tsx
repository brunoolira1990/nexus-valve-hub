import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SecoesIntegracoesExternas } from '@/components/financeiro/SecoesIntegracoesExternas';
import { AnaliseFinanceiraIndicadores } from '@/components/financeiro/AnaliseFinanceiraIndicadores';
import { analiseFinanceiraService } from '@/services/api/analiseFinanceira';

vi.mock('@/services/api/analiseFinanceira', () => ({
  analiseFinanceiraService: {
    capacidadeIntegracoes: vi.fn(),
    listConsultasExternas: vi.fn(),
    solicitarConsultaCadastral: vi.fn(),
    solicitarConsultaBuro: vi.fn(),
  },
}));

const capacidadeOff = {
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

describe('SecoesIntegracoesExternas fundação B2/B3', () => {
  beforeEach(() => {
    vi.mocked(analiseFinanceiraService.capacidadeIntegracoes).mockReset();
    vi.mocked(analiseFinanceiraService.listConsultasExternas).mockReset();
    const svc = analiseFinanceiraService as unknown as {
      solicitarConsultaCadastral: ReturnType<typeof vi.fn>;
      solicitarConsultaBuro: ReturnType<typeof vi.fn>;
    };
    svc.solicitarConsultaCadastral.mockReset();
    svc.solicitarConsultaBuro.mockReset();
  });

  it('mostra cadastral não configurado e birô não contratado', () => {
    render(<SecoesIntegracoesExternas capacidade={capacidadeOff} carregarCapability={false} />);
    expect(screen.getByTestId('dossie-cadastral-placeholder')).toHaveTextContent(
      'ainda não está configurada',
    );
    expect(screen.getByTestId('dossie-buro-placeholder')).toHaveTextContent('Não há birô');
    expect(screen.getByTestId('dossie-decisao-manual')).toHaveTextContent('manual');
    expect(screen.getByTestId('dossie-btn-consultar-cadastral')).toBeDisabled();
    expect(screen.getByTestId('dossie-btn-consultar-buro')).toBeDisabled();
  });

  it('não exibe score, dívidas, capital ou provider ativo fictício', () => {
    const { container } = render(
      <SecoesIntegracoesExternas capacidade={capacidadeOff} carregarCapability={false} />,
    );
    const txt = container.textContent || '';
    expect(txt).not.toMatch(/score/i);
    expect(txt).not.toMatch(/dívida/i);
    expect(txt).not.toMatch(/capital social/i);
    expect(txt).not.toMatch(/serasa|spc|quod|receitaws/i);
    expect(txt).not.toContain('"score"');
  });

  it('botões desabilitados não disparam consulta ao clicar', () => {
    const svc = analiseFinanceiraService as unknown as {
      solicitarConsultaCadastral: ReturnType<typeof vi.fn>;
      solicitarConsultaBuro: ReturnType<typeof vi.fn>;
    };
    render(<SecoesIntegracoesExternas capacidade={capacidadeOff} carregarCapability={false} />);
    fireEvent.click(screen.getByTestId('dossie-btn-consultar-cadastral'));
    fireEvent.click(screen.getByTestId('dossie-btn-consultar-buro'));
    expect(svc.solicitarConsultaCadastral).not.toHaveBeenCalled();
    expect(svc.solicitarConsultaBuro).not.toHaveBeenCalled();
    expect(analiseFinanceiraService.listConsultasExternas).not.toHaveBeenCalled();
    expect(analiseFinanceiraService.capacidadeIntegracoes).not.toHaveBeenCalled();
  });

  it('capability loading', async () => {
    let resolve!: (v: typeof capacidadeOff) => void;
    vi.mocked(analiseFinanceiraService.capacidadeIntegracoes).mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    render(<SecoesIntegracoesExternas />);
    expect(screen.getByTestId('dossie-integracoes-loading')).toBeInTheDocument();
    resolve(capacidadeOff);
    await waitFor(() => expect(screen.queryByTestId('dossie-integracoes-loading')).not.toBeInTheDocument());
  });

  it('erro de capability não habilita botões e não chama consulta', async () => {
    vi.mocked(analiseFinanceiraService.capacidadeIntegracoes).mockRejectedValue(new Error('Network'));
    render(<SecoesIntegracoesExternas />);
    await waitFor(() => expect(screen.getByTestId('dossie-integracoes-erro')).toBeInTheDocument());
    expect(screen.getByTestId('dossie-btn-consultar-cadastral')).toBeDisabled();
    expect(screen.getByTestId('dossie-btn-consultar-buro')).toBeDisabled();
    fireEvent.click(screen.getByTestId('dossie-btn-consultar-cadastral'));
    expect(analiseFinanceiraService.listConsultasExternas).not.toHaveBeenCalled();
  });

  it('abrir seção não dispara listConsultasExternas', () => {
    render(<SecoesIntegracoesExternas capacidade={capacidadeOff} carregarCapability={false} />);
    expect(analiseFinanceiraService.listConsultasExternas).not.toHaveBeenCalled();
  });
});

describe('Dossiê com B1 + integrações desabilitadas', () => {
  it('mantém indicadores B1 e seções externas desabilitadas', () => {
    render(
      <AnaliseFinanceiraIndicadores
        snapshot={{
          schema_versao: 2,
          qualidade: { status: 'COMPLETA', mensagem: 'ok', indisponiveis: [] },
          indicadores: {
            comercial: { fonte: 'NFE_SAIDA_PRODUCAO', periodos: { TOTAL: { quantidade_vendas: 1, valor_vendido: '10' } } },
            contas_receber: { saldo_aberto: '0' },
            exposicao: { atual: '0', projetada: '10', valor_proposta: '10' },
            limite: { cadastrado: '100', ambiguo: false },
            baixas: { periodos: {} },
            pedidos_nao_faturados: { valor_residual: '0', quantidade_pedidos: 0 },
          },
        }}
        capacidadeIntegracoes={capacidadeOff}
        carregarCapabilityIntegracoes={false}
      />,
    );
    expect(screen.getByTestId('dossie-comercial')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-exposicao')).toBeInTheDocument();
    expect(screen.getByTestId('dossie-btn-consultar-cadastral')).toBeDisabled();
    expect(screen.getByTestId('dossie-decisao-manual')).toBeInTheDocument();
  });
});
