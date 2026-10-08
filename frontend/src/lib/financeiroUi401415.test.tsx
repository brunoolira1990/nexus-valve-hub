import { describe, expect, it } from 'vitest';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_MESSAGES,
  FINANCEIRO_OPERATIONAL_MESSAGES,
  getTituloFinanceiroAcoes,
  getTituloFinanceiroOperationalMessages,
  type TituloFinanceiroOperacional,
} from '@/lib/financeiroUi';

const tituloEmAbertoReceber = (): TituloFinanceiroOperacional => ({
  status: 'EM_ABERTO',
  valor_aberto: '1500.00',
  valor_baixado: '0.00',
  pode_baixar: true,
  pode_editar: true,
  pode_cancelar: true,
  possui_baixa_ativa: false,
  pode_estornar_baixa: false,
});

const tituloEmAbertoPagar = (): TituloFinanceiroOperacional => ({
  status: 'EM_ABERTO',
  valor_aberto: '5000.00',
  valor_baixado: '0.00',
  pode_baixar: true,
  pode_editar: true,
  pode_cancelar: true,
  possui_baixa_ativa: false,
  pode_estornar_baixa: false,
});

describe('financeiroUi 4.0.14.1.5 — detalhe financeiro por status', () => {
  it('CR em aberto não mostra mensagem já foi baixado', () => {
    const { messages } = getTituloFinanceiroOperationalMessages(tituloEmAbertoReceber(), 'RECEBER');
    expect(messages.join(' ')).not.toContain('já foi baixado');
    expect(messages.join(' ')).not.toContain(FINANCEIRO_MESSAGES.tituloBaixado);
  });

  it('CR em aberto mostra mensagem de título em aberto', () => {
    const { messages } = getTituloFinanceiroOperationalMessages(tituloEmAbertoReceber(), 'RECEBER');
    expect(messages).toContain(FINANCEIRO_OPERATIONAL_MESSAGES.tituloEmAbertoReceber);
  });

  it('CR em aberto mostra botão Baixar recebimento', () => {
    const acoes = getTituloFinanceiroAcoes(tituloEmAbertoReceber(), 'RECEBER');
    expect(acoes.some((a) => a.id === 'baixar' && a.label === FINANCEIRO_ACTION_LABELS.baixarRecebimento)).toBe(
      true,
    );
  });

  it('CR recebida mostra mensagem já foi recebido', () => {
    const titulo: TituloFinanceiroOperacional = {
      status: 'RECEBIDO',
      valor_aberto: '0.00',
      valor_baixado: '1500.00',
      possui_baixa_ativa: true,
      pode_estornar_baixa: true,
    };
    const { messages } = getTituloFinanceiroOperationalMessages(titulo, 'RECEBER');
    expect(messages).toContain(FINANCEIRO_OPERATIONAL_MESSAGES.recebidoEstorno);
  });

  it('CR recebida mostra Estornar baixa', () => {
    const titulo: TituloFinanceiroOperacional = {
      status: 'RECEBIDO',
      valor_aberto: '0.00',
      valor_baixado: '1500.00',
      possui_baixa_ativa: true,
      pode_estornar_baixa: true,
    };
    const acoes = getTituloFinanceiroAcoes(titulo, 'RECEBER');
    expect(acoes.some((a) => a.id === 'estornar_baixa')).toBe(true);
  });

  it('CP em aberto não mostra mensagem já foi baixado', () => {
    const { messages } = getTituloFinanceiroOperationalMessages(tituloEmAbertoPagar(), 'PAGAR');
    expect(messages.join(' ')).not.toContain('já foi baixado');
  });

  it('CP em aberto mostra mensagem de título em aberto', () => {
    const { messages } = getTituloFinanceiroOperationalMessages(tituloEmAbertoPagar(), 'PAGAR');
    expect(messages).toContain(FINANCEIRO_OPERATIONAL_MESSAGES.tituloEmAbertoPagar);
  });

  it('CP em aberto mostra botão Baixar pagamento', () => {
    const acoes = getTituloFinanceiroAcoes(tituloEmAbertoPagar(), 'PAGAR');
    expect(acoes.some((a) => a.id === 'baixar' && a.label === FINANCEIRO_ACTION_LABELS.baixarPagamento)).toBe(
      true,
    );
  });

  it('CP paga mostra mensagem já foi pago', () => {
    const titulo: TituloFinanceiroOperacional = {
      status: 'PAGO',
      valor_aberto: '0.00',
      valor_baixado: '5000.00',
      possui_baixa_ativa: true,
      pode_estornar_baixa: true,
    };
    const { messages } = getTituloFinanceiroOperationalMessages(titulo, 'PAGAR');
    expect(messages).toContain(FINANCEIRO_OPERATIONAL_MESSAGES.pagoEstorno);
  });

  it('título cancelado mostra mensagem de cancelamento', () => {
    const titulo: TituloFinanceiroOperacional = {
      status: 'CANCELADO',
      cancelado: true,
      valor_aberto: '100.00',
      valor_baixado: '0.00',
    };
    const { messages } = getTituloFinanceiroOperationalMessages(titulo, 'RECEBER');
    expect(messages).toEqual([FINANCEIRO_OPERATIONAL_MESSAGES.cancelado]);
  });

  it('título parcial mostra mensagem de saldo em aberto', () => {
    const titulo: TituloFinanceiroOperacional = {
      status: 'PARCIALMENTE_RECEBIDO',
      valor_aberto: '500.00',
      valor_baixado: '1000.00',
      possui_baixa_ativa: true,
      pode_baixar: true,
    };
    const { messages } = getTituloFinanceiroOperationalMessages(titulo, 'RECEBER');
    expect(messages).toContain(FINANCEIRO_OPERATIONAL_MESSAGES.parcialRecebido);
  });

  it('Estornar baixa só aparece se houver baixa ativa', () => {
    const semBaixa = getTituloFinanceiroAcoes(tituloEmAbertoReceber(), 'RECEBER');
    expect(semBaixa.some((a) => a.id === 'estornar_baixa')).toBe(false);

    const comBaixa = getTituloFinanceiroAcoes(
      {
        status: 'PARCIALMENTE_PAGO',
        valor_aberto: '100.00',
        valor_baixado: '400.00',
        possui_baixa_ativa: true,
        pode_estornar_baixa: true,
        pode_baixar: true,
      },
      'PAGAR',
    );
    expect(comBaixa.some((a) => a.id === 'estornar_baixa')).toBe(true);
  });

  it('Abater por devolução só aparece se houver saldo em aberto', () => {
    const aberto = getTituloFinanceiroAcoes(
      { ...tituloEmAbertoPagar(), pode_abater: true },
      'PAGAR',
    );
    expect(aberto.some((a) => a.id === 'abater_devolucao')).toBe(true);

    const quitado = getTituloFinanceiroAcoes(
      {
        status: 'PAGO',
        valor_aberto: '0.00',
        valor_baixado: '5000.00',
        pode_abater: false,
        possui_baixa_ativa: true,
      },
      'PAGAR',
    );
    expect(quitado.some((a) => a.id === 'abater_devolucao')).toBe(false);
  });

  it('Aplicar crédito só aparece se houver saldo em aberto', () => {
    const aberto = getTituloFinanceiroAcoes(
      { ...tituloEmAbertoReceber(), pode_aplicar_credito: true },
      'RECEBER',
    );
    expect(aberto.some((a) => a.id === 'aplicar_credito')).toBe(true);

    const cancelado = getTituloFinanceiroAcoes(
      {
        status: 'CANCELADO',
        cancelado: true,
        valor_aberto: '100.00',
        pode_aplicar_credito: false,
      },
      'RECEBER',
    );
    expect(cancelado.some((a) => a.id === 'aplicar_credito')).toBe(false);
  });
});
