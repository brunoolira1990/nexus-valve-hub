import { describe, expect, it } from 'vitest';
import {
  FINANCEIRO_ACTION_LABELS,
  FINANCEIRO_STATUS_LABELS,
  labelStatusFinanceiro,
  labelTipoLancamentoPagar,
  labelTipoTributo,
  statusBadgeFinanceiro,
  tituloModoConfig,
} from '@/lib/financeiroUi';

describe('financeiroUi 4.0.14', () => {
  it('status amigáveis sem enum cru', () => {
    expect(labelStatusFinanceiro('PARCIALMENTE_RECEBIDO')).toBe('Parcialmente recebido');
    expect(labelStatusFinanceiro('EM_ABERTO')).toBe('Em aberto');
    expect(FINANCEIRO_STATUS_LABELS.PARCIALMENTE_PAGO).toBe('Parcialmente pago');
  });

  it('prioriza status_label da API', () => {
    expect(statusBadgeFinanceiro({ status: 'EM_ABERTO', status_label: 'Em aberto' })).toBe('Em aberto');
  });

  it('ações operacionais', () => {
    expect(FINANCEIRO_ACTION_LABELS.baixarRecebimento).toBe('Baixar recebimento');
    expect(FINANCEIRO_ACTION_LABELS.estornarBaixa).toBe('Estornar baixa');
  });

  it('config por modo receber/pagar', () => {
    expect(tituloModoConfig('RECEBER').tituloPagina).toBe('Contas a Receber');
    expect(tituloModoConfig('RECEBER').novoLabel).toBe('Nova conta a receber');
    expect(tituloModoConfig('PAGAR').contraparteLabel).toBe('Fornecedor');
  });

  it('tipos de lançamento e tributo amigáveis', () => {
    expect(labelTipoLancamentoPagar('TRIBUTO_IMPOSTO')).toBe('Tributo / Imposto');
    expect(labelTipoTributo('ICMS')).toBe('ICMS');
    expect(FINANCEIRO_ACTION_LABELS.novaDespesa).toBe('Nova despesa');
    expect(FINANCEIRO_ACTION_LABELS.novoTributo).toBe('Novo tributo a pagar');
  });

  it('financeiro não usa cadastro de condições de pagamento', () => {
    expect('novaCondicaoPagamento' in FINANCEIRO_ACTION_LABELS).toBe(false);
    expect('condicoesPagamento' in FINANCEIRO_ACTION_LABELS).toBe(false);
  });
});
