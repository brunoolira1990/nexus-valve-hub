import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AnalisesFinanceirasPage from '@/pages/financeiro/AnalisesFinanceirasPage';
import {
  AnaliseFinanceiraIndicadores,
  AVISO_QUALIDADE_PARCIAL,
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
  },
}));

const snapshotCompleto = {
  qualidade_dados: 'PARCIAL',
  dados_indisponiveis: ['percentual_pontualidade', 'atraso_medio_dias'],
  data_corte: '2026-07-24',
  limite_credito_cadastrado: { disponivel: true, valor: '10000.00' },
  contas_receber: {
    disponivel: true,
    saldo_aberto: '500.00',
    saldo_a_vencer: '300.00',
    saldo_vencido: '200.00',
    quantidade_titulos_vencidos: 2,
  },
  pedidos_nao_faturados: { disponivel: true, valor_residual: '150.00' },
  exposicao: { atual: '650.00', valor_proposta: '200.00', projetada: '850.00' },
  percentual_pontualidade: { disponivel: false, valor: null },
};

describe('AnaliseFinanceiraIndicadores', () => {
  it('apresenta valores estruturados sem JSON bruto', () => {
    const { container } = render(<AnaliseFinanceiraIndicadores snapshot={snapshotCompleto} />);
    expect(screen.getByTestId('analise-fin-indicadores')).toBeInTheDocument();
    expect(screen.getByTestId('analise-fin-aviso-parcial')).toHaveTextContent(AVISO_QUALIDADE_PARCIAL);
    expect(screen.getByText(/Limite de crédito cadastrado/i)).toBeInTheDocument();
    expect(screen.getByText(/Exposição projetada/i)).toBeInTheDocument();
    expect(screen.getByTestId('analise-fin-indisponiveis')).toHaveTextContent('Indisponível');
    expect(container.textContent).not.toMatch(/"qualidade_dados"/);
    expect(container.textContent).not.toContain('null');
    expect(container.textContent).not.toContain('undefined');
  });

  it('mostra Indisponível quando métrica não disponível', () => {
    render(
      <AnaliseFinanceiraIndicadores
        snapshot={{
          qualidade_dados: 'PARCIAL',
          dados_indisponiveis: ['percentual_pontualidade'],
          limite_credito_cadastrado: { disponivel: false, valor: null },
          contas_receber: { disponivel: false },
          pedidos_nao_faturados: { disponivel: false },
          exposicao: {},
        }}
      />,
    );
    expect(screen.getAllByText('Indisponível').length).toBeGreaterThan(0);
  });

  it('resumo restrito não exibe saldos', () => {
    render(
      <AnaliseFinanceiraIndicadores
        snapshot={{ qualidade_dados: 'PARCIAL', resumo_restrito: true, dados_indisponiveis: [] }}
      />,
    );
    expect(screen.queryByText(/Saldo total a receber/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('analise-fin-aviso-parcial')).toBeInTheDocument();
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
    expect(screen.getByTestId('analise-fin-reanalise')).toBeInTheDocument();
    expect(screen.getByTestId('analise-fin-status')).toHaveTextContent('Não solicitada');
  });

  it('solicitar análise', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockResolvedValue({
      situacao: {
        avaliacao: {
          exige_liberacao: true,
          a_vista: false,
          valida: false,
          motivo_codigo: 'SEM_APROVACAO',
          motivo: 'Precisa',
          condicao_atual: null,
          analise_id: null,
        },
        ultima_analise_id: null,
        ultima_analise_status: null,
        analise_ativa_id: null,
        reanalise_necessaria: true,
        permissoes: { pode_solicitar: true },
      },
      ultima: null,
      historico: [],
    });
    vi.mocked(analiseFinanceiraService.solicitar).mockResolvedValue({
      id: 1,
      proposta: 10,
      cliente: 1,
      status: 'PENDENTE',
      versao: 1,
      solicitada_em: '2026-07-24T12:00:00Z',
      valor_solicitado: '200.00',
    });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => screen.getByTestId('analise-fin-solicitar'));
    fireEvent.click(screen.getByTestId('analise-fin-solicitar'));
    await waitFor(() => expect(analiseFinanceiraService.solicitar).toHaveBeenCalled());
  });

  it('estado PENDENTE no resumo', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockResolvedValue({
      situacao: {
        avaliacao: {
          exige_liberacao: true,
          a_vista: false,
          valida: false,
          motivo_codigo: 'ANALISE_PENDENTE',
          motivo: 'Em andamento',
          condicao_atual: null,
          analise_id: 5,
        },
        ultima_analise_id: 5,
        ultima_analise_status: 'PENDENTE',
        analise_ativa_id: 5,
        reanalise_necessaria: true,
        permissoes: { pode_solicitar: true },
      },
      ultima: {
        id: 5,
        proposta: 10,
        cliente: 1,
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
      },
      historico: [],
    });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => expect(screen.getByTestId('analise-fin-status')).toHaveTextContent('Aguardando análise'));
  });

  it('sem permissão não vê solicitar', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockResolvedValue({
      situacao: {
        avaliacao: {
          exige_liberacao: true,
          a_vista: false,
          valida: false,
          motivo_codigo: 'SEM_APROVACAO',
          motivo: 'Precisa',
          condicao_atual: null,
          analise_id: null,
        },
        ultima_analise_id: null,
        ultima_analise_status: null,
        analise_ativa_id: null,
        reanalise_necessaria: true,
        permissoes: { pode_solicitar: false },
      },
      ultima: null,
      historico: [],
    });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => screen.getByTestId('analise-fin-sem-permissao-solicitar'));
    expect(screen.queryByTestId('analise-fin-solicitar')).not.toBeInTheDocument();
  });

  it('erro 403 tratado', async () => {
    const err = { response: { status: 403, data: { detail: 'Sem permissão.' } } };
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockRejectedValue(err);
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => expect(screen.getByTestId('analise-fin-erro')).toHaveTextContent(PERMISSION_DENIED_MESSAGE));
  });

  it('erro de rede não interpreta como aprovação', async () => {
    vi.mocked(analiseFinanceiraService.situacaoProposta).mockRejectedValue({ message: 'Network Error' });
    render(<PropostaAnaliseFinanceiraPanel propostaId={10} />);
    await waitFor(() => expect(screen.getByTestId('analise-fin-erro')).toBeInTheDocument());
    expect(screen.getByTestId('analise-fin-status')).toHaveTextContent('Não solicitada');
    expect(screen.queryByText(/^Aprovada$/i)).not.toBeInTheDocument();
  });

  it('não carrega sem proposta', () => {
    render(<PropostaAnaliseFinanceiraPanel propostaId={null} />);
    expect(screen.getByTestId('analise-fin-sem-proposta')).toBeInTheDocument();
    expect(analiseFinanceiraService.situacaoProposta).not.toHaveBeenCalled();
  });
});

describe('AnalisesFinanceirasPage', () => {
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
    snapshot_indicadores: snapshotCompleto,
    permissoes: { pode_decidir: true, pode_ver_detalhe_financeiro: true },
  };

  beforeEach(() => {
    vi.mocked(analiseFinanceiraService.list).mockReset();
    vi.mocked(analiseFinanceiraService.getById).mockReset();
    vi.mocked(analiseFinanceiraService.aprovar).mockReset();
    vi.mocked(analiseFinanceiraService.aprovarComAjuste).mockReset();
    vi.mocked(analiseFinanceiraService.naoAprovar).mockReset();
    vi.mocked(analiseFinanceiraService.list).mockResolvedValue({ count: 1, results: [baseAnalise] });
    vi.mocked(analiseFinanceiraService.getById).mockResolvedValue(baseAnalise);
  });

  it('fila financeira e abrir detalhe com indicadores estruturados', async () => {
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('analise-fin-fila')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => expect(screen.getByTestId('analise-fin-detalhe')).toBeInTheDocument());
    expect(screen.getByTestId('analise-fin-indicadores')).toBeInTheDocument();
    expect(screen.getByTestId('analise-fin-aviso-parcial')).toBeInTheDocument();
    expect(screen.getByTestId('analise-fin-acoes')).toBeInTheDocument();
    expect(screen.queryByText(/"exposicao"/)).not.toBeInTheDocument();
  });

  it('aprovar como solicitado', async () => {
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

  it('aprovar com ajuste envia justificativa', async () => {
    vi.mocked(analiseFinanceiraService.aprovarComAjuste).mockResolvedValue({
      ...baseAnalise,
      status: 'APROVADA_COM_AJUSTE',
    });
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('analise-fin-abrir-7'));
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => screen.getByTestId('analise-fin-justificativa'));
    fireEvent.change(screen.getByTestId('analise-fin-justificativa'), {
      target: { value: 'Entrada obrigatória' },
    });
    fireEvent.click(screen.getByTestId('analise-fin-aprovar-ajuste'));
    await waitFor(() =>
      expect(analiseFinanceiraService.aprovarComAjuste).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ justificativa: 'Entrada obrigatória' }),
      ),
    );
  });

  it('não aprovar', async () => {
    vi.mocked(analiseFinanceiraService.naoAprovar).mockResolvedValue({
      ...baseAnalise,
      status: 'NAO_APROVADA',
    });
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('analise-fin-abrir-7'));
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => screen.getByTestId('analise-fin-justificativa'));
    fireEvent.change(screen.getByTestId('analise-fin-justificativa'), { target: { value: 'Risco' } });
    fireEvent.click(screen.getByTestId('analise-fin-nao-aprovar'));
    await waitFor(() => expect(analiseFinanceiraService.naoAprovar).toHaveBeenCalledWith(7, 'Risco'));
  });

  it('sem permissão de decisão não vê ações', async () => {
    vi.mocked(analiseFinanceiraService.getById).mockResolvedValue({
      ...baseAnalise,
      permissoes: { pode_decidir: false, pode_ver_detalhe_financeiro: false },
      snapshot_indicadores: { qualidade_dados: 'PARCIAL', resumo_restrito: true },
    });
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('analise-fin-abrir-7'));
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => screen.getByTestId('analise-fin-detalhe'));
    expect(screen.queryByTestId('analise-fin-acoes')).not.toBeInTheDocument();
    expect(screen.queryByText(/Saldo total a receber/i)).not.toBeInTheDocument();
  });

  it('erro 403 na ação é tratado', async () => {
    vi.mocked(analiseFinanceiraService.aprovar).mockRejectedValue({
      response: { status: 403, data: { detail: 'Você não tem permissão para decidir análises financeiras.' } },
    });
    render(
      <MemoryRouter>
        <AnalisesFinanceirasPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('analise-fin-abrir-7'));
    fireEvent.click(screen.getByTestId('analise-fin-abrir-7'));
    await waitFor(() => screen.getByTestId('analise-fin-aprovar'));
    fireEvent.click(screen.getByTestId('analise-fin-aprovar'));
    await waitFor(() =>
      expect(screen.getByTestId('analise-fin-action-error')).toHaveTextContent(PERMISSION_DENIED_MESSAGE),
    );
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
    expect(msg).not.toContain('SEM_APROVACAO');
  });
});
