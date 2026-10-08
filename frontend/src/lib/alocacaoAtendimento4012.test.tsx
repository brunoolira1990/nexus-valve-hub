import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { AlocacaoAtendimentoGerenciarPanel } from '@/components/comercial/AlocacaoAtendimentoGerenciarPanel';
import type { ResumoAtendimentoOperacional } from '@/types/atendimentoOperacional';

const resumoVazio: ResumoAtendimentoOperacional = {
  tem_alocacao: false,
  badges: [{ label: 'Atendimento não definido', status: 'nao_definido', variant: 'neutral' }],
  mensagem:
    'Atendimento operacional ainda não definido. Use esta seção para informar retirada no fornecedor, entrega direta, entrada pendente ou entrada conciliada.',
};

vi.mock('@/services/api/alocacaoAtendimento', () => ({
  alocacaoAtendimentoService: {
    listByPedidoVenda: vi.fn(async () => ({
      alocacoes: [],
      count: 0,
      resumo_atendimento_operacional: resumoVazio,
    })),
    listByNFeSaida: vi.fn(async () => ({
      alocacoes: [],
      count: 0,
      resumo_atendimento_operacional: resumoVazio,
    })),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));

vi.mock('@/services/api/fornecedores', () => ({
  fornecedoresService: {
    getAll: vi.fn(async () => []),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe('ERP 4.0.12 — alocação atendimento', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exibe aviso de que não movimenta estoque/financeiro', async () => {
    render(
      <AlocacaoAtendimentoGerenciarPanel
        pedidoVendaId={1}
        itens={[
          {
            id: 10,
            produto_id: 5,
            produto_nome: 'Válvula',
            quantidade: 2,
            valor_unitario: 100,
          },
        ]}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByText(/não movimenta estoque, não gera financeiro/i),
      ).toBeInTheDocument();
    });
  });

  it('mostra botão Adicionar alocação', async () => {
    render(<AlocacaoAtendimentoGerenciarPanel pedidoVendaId={1} itens={[]} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Adicionar alocação/i })).toBeInTheDocument();
    });
  });

  it('abre formulário com campos principais', async () => {
    render(
      <AlocacaoAtendimentoGerenciarPanel
        pedidoVendaId={1}
        itens={[
          {
            id: 10,
            produto_id: 5,
            produto_nome: 'Válvula',
            quantidade: 2,
            valor_unitario: 100,
          },
        ]}
      />,
    );
    await waitFor(() => screen.getByRole('button', { name: /Adicionar alocação/i }));
    fireEvent.click(screen.getByRole('button', { name: /Adicionar alocação/i }));
    expect(screen.getByText(/Tipo de atendimento/i)).toBeInTheDocument();
    expect(screen.getByText(/Status entrada fiscal/i)).toBeInTheDocument();
    expect(screen.getByText(/Retirada no fornecedor/i)).toBeInTheDocument();
  });

  it('resumo null não quebra painel NF-e', async () => {
    const { container } = render(
      <AlocacaoAtendimentoGerenciarPanel nfeSaidaId={99} resumoInicial={null} />,
    );
    await waitFor(() => {
      expect(container.textContent).toMatch(/Gerenciar|Alocações|não movimenta/i);
    });
  });
});
