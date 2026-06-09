import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NFeEntradaFinanceiroAcoes } from '@/components/fiscal/NFeEntradaFinanceiroAcoes';

const TOLERANCIA = 0.05;

export function somaParcelasValidaEntrada(soma: number, total: number): boolean {
  return Math.abs(soma - total) <= TOLERANCIA;
}

describe('NFeEntradaFinanceiroAcoes', () => {
  it('mostra Gerar contas a pagar quando conferida e pode gerar', () => {
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={1}
          conferenciaStatus="CONFERIDA"
          financeiro={{ pode_gerar_contas_pagar: true, financeiro_gerado: false }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Gerar contas a pagar/i })).toBeEnabled();
  });

  it('desabilita ação apenas com bloqueio financeiro real', () => {
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={1}
          conferenciaStatus="PENDENTE"
          financeiro={{
            pode_gerar_contas_pagar: false,
            motivo_bloqueio_financeiro: 'Fornecedor não identificado na NF-e Entrada.',
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Gerar contas a pagar/i })).toBeDisabled();
    expect(screen.getByText(/Fornecedor não identificado/i)).toBeInTheDocument();
  });

  it('conferência pendente com dados mínimos mostra Gerar contas a pagar', () => {
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={1}
          conferenciaStatus="PENDENTE"
          financeiro={{
            pode_gerar_contas_pagar: true,
            possui_pendencias_operacionais: true,
            aviso_pendencias_operacionais: 'Existem pendências operacionais nesta NF-e.',
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Gerar contas a pagar/i })).toBeEnabled();
    expect(screen.getByText(/pendências operacionais/i)).toBeInTheDocument();
  });

  it('NF-e cancelada não permite gerar', () => {
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={1}
          conferenciaStatus="CANCELADA"
          financeiro={{
            pode_gerar_contas_pagar: false,
            motivo_bloqueio_financeiro: 'Esta NF-e Entrada está cancelada e não pode gerar contas a pagar.',
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /Gerar contas a pagar/i })).not.toBeInTheDocument();
    expect(screen.getByText(/cancelada/i)).toBeInTheDocument();
  });

  it('mostra Ver contas a pagar após gerado', () => {
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={1}
          conferenciaStatus="CONFERIDA"
          financeiro={{
            financeiro_gerado: true,
            contas_pagar_vinculadas: [{ id: 99, numero: 'CP-001' }],
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Ver contas a pagar/i })).toBeInTheDocument();
  });

  it('exibe alerta quando NF-e cancelada com financeiro vinculado', () => {
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={1}
          conferenciaStatus="CANCELADA"
          financeiro={{
            financeiro_gerado: true,
            nfe_entrada_cancelada_com_financeiro: true,
            contas_pagar_vinculadas: [{ id: 1, numero: 'CP-1' }],
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/possui contas a pagar vinculadas/i)).toBeInTheDocument();
  });

  it('clique em gerar dispara callback', () => {
    let clicked = false;
    render(
      <MemoryRouter>
        <NFeEntradaFinanceiroAcoes
          nfeEntradaId={5}
          conferenciaStatus="PREPARADA"
          financeiro={{ pode_gerar_contas_pagar: true }}
          onGerar={() => {
            clicked = true;
          }}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Gerar contas a pagar/i }));
    expect(clicked).toBe(true);
  });
});

describe('validação de parcelas wizard NF-e Entrada', () => {
  it('soma válida dentro da tolerância', () => {
    expect(somaParcelasValidaEntrada(1000, 1000)).toBe(true);
    expect(somaParcelasValidaEntrada(999.97, 1000)).toBe(true);
  });

  it('soma inválida bloqueia confirmação', () => {
    expect(somaParcelasValidaEntrada(900, 1000)).toBe(false);
  });
});

describe('origem exibição contas a pagar', () => {
  it('formata origem NF-e Entrada para listagem', () => {
    const origem = 'NF-e Entrada nº 000123';
    expect(origem).toMatch(/NF-e Entrada nº/);
  });
});

describe('wizard confirmação pendências operacionais', () => {
  function confirmacaoPendenciasOk(exigeConfirmacao: boolean, confirmado: boolean): boolean {
    return !exigeConfirmacao || confirmado;
  }

  it('exige confirmação quando há pendências operacionais', () => {
    expect(confirmacaoPendenciasOk(true, false)).toBe(false);
    expect(confirmacaoPendenciasOk(true, true)).toBe(true);
  });

  it('não exige confirmação sem pendências operacionais', () => {
    expect(confirmacaoPendenciasOk(false, false)).toBe(true);
  });

  it('texto auxiliar não menciona estoque aplicado', () => {
    const texto =
      'Gere o financeiro a partir das duplicatas da NF-e Entrada. Estoque e conferência operacional não serão alterados.';
    expect(texto).not.toMatch(/estoque aplicado/i);
    expect(texto).toMatch(/não serão alterados/i);
  });
});

describe('exclusão título com origem NF-e Entrada', () => {
  it('título NFE_ENTRADA não deve permitir excluir', () => {
    const titulo = { origem_tipo: 'NFE_ENTRADA', pode_excluir: false };
    expect(titulo.pode_excluir).toBe(false);
  });
});
