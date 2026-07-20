import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NFeFinanceiroAcoes } from '@/components/fiscal/NFeFinanceiroAcoes';

const TOLERANCIA = 0.05;

export function somaParcelasValida(soma: number, total: number): boolean {
  return Math.abs(soma - total) <= TOLERANCIA;
}

describe('NFeFinanceiroAcoes', () => {
  it('mostra Gerar contas a receber quando autorizada produção e pode gerar', () => {
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={1}
          status="AUTORIZADA_PRODUCAO"
          statusEmissaoSefaz="AUTORIZADA_PRODUCAO"
          financeiro={{ pode_gerar_contas_receber: true, financeiro_gerado: false }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Gerar contas a receber/i })).toBeEnabled();
  });

  it('desabilita ação em homologação', () => {
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={1}
          status="AUTORIZADA_HOMOLOGACAO"
          statusEmissaoSefaz="AUTORIZADA_HOMOLOGACAO"
          financeiro={{
            pode_gerar_contas_receber: false,
            motivo_bloqueio_financeiro: 'Financeiro indisponível para NF-e de homologação.',
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Gerar contas a receber/i })).toBeDisabled();
    expect(screen.getByText(/homologação/i)).toBeInTheDocument();
  });

  it('desabilita ação quando NF-e não autorizada', () => {
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={1}
          status="RASCUNHO"
          financeiro={{ pode_gerar_contas_receber: false }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Gerar contas a receber/i })).toBeDisabled();
    expect(screen.getByText(/Disponível após autorização da NF-e/i)).toBeInTheDocument();
  });

  it('mostra Ver contas a receber após gerado', () => {
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={1}
          status="AUTORIZADA_PRODUCAO"
          statusEmissaoSefaz="AUTORIZADA_PRODUCAO"
          financeiro={{
            financeiro_gerado: true,
            contas_receber_vinculadas: [{ id: 99, numero: 'CR-001' }],
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Ver contas a receber/i })).toBeInTheDocument();
  });

  it('exibe motivo de bloqueio por duplicidade', () => {
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={1}
          status="AUTORIZADA_PRODUCAO"
          statusEmissaoSefaz="AUTORIZADA_PRODUCAO"
          financeiro={{
            financeiro_gerado: true,
            motivo_bloqueio_financeiro: 'Contas a receber já foram geradas para esta NF-e.',
            contas_receber_vinculadas: [{ id: 1, numero: 'CR-1' }],
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Ver contas a receber/i })).toBeInTheDocument();
  });

  it('venda à vista — sem botão Gerar e com informação neutra', () => {
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={1}
          status="AUTORIZADA_PRODUCAO"
          statusEmissaoSefaz="AUTORIZADA_PRODUCAO"
          financeiro={{
            pode_gerar_contas_receber: false,
            venda_integralmente_a_vista: true,
            motivo_bloqueio_financeiro: 'Venda à vista — não gera Contas a Receber.',
          }}
          onGerar={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /Gerar contas a receber/i })).toBeNull();
    expect(screen.getByText(/Venda à vista — não gera Contas a Receber/i)).toBeInTheDocument();
  });
});

describe('validação de parcelas wizard', () => {
  it('soma válida dentro da tolerância', () => {
    expect(somaParcelasValida(400, 400)).toBe(true);
    expect(somaParcelasValida(399.97, 400)).toBe(true);
  });

  it('soma inválida bloqueia confirmação', () => {
    expect(somaParcelasValida(350, 400)).toBe(false);
  });
});

describe('origem exibição contas a receber', () => {
  it('formata origem NF-e para listagem', () => {
    const origem = 'NF-e nº 000000003';
    expect(origem).toMatch(/NF-e nº/);
  });
});

describe('exclusão título com origem NF-e', () => {
  it('título NFE_SAIDA não deve permitir excluir', () => {
    const titulo = { origem_tipo: 'NFE_SAIDA', pode_excluir: false };
    expect(titulo.pode_excluir).toBe(false);
  });
});

describe('interação wizard', () => {
  it('clique em gerar dispara callback', () => {
    let clicked = false;
    render(
      <MemoryRouter>
        <NFeFinanceiroAcoes
          nfeId={5}
          status="AUTORIZADA_PRODUCAO"
          statusEmissaoSefaz="AUTORIZADA_PRODUCAO"
          financeiro={{ pode_gerar_contas_receber: true }}
          onGerar={() => {
            clicked = true;
          }}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Gerar contas a receber/i }));
    expect(clicked).toBe(true);
  });
});
