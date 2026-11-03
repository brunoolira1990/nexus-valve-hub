import { describe, expect, it } from 'vitest';

import {
  cotacaoStatusToSteps,
  nfeEntradaStatusToSteps,
  nfeSaidaStatusToSteps,
  pedidoCompraStatusToSteps,
  pedidoVendaStatusToSteps,
  propostaStatusToSteps,
} from './statusPipelineHelpers';

describe('propostaStatusToSteps', () => {
  it('mapeia a progressão cotacao → aprovada → pedido_venda', () => {
    expect(propostaStatusToSteps({ status: 'RASCUNHO' }).currentKey).toBe('cotacao');
    expect(propostaStatusToSteps({ status: 'APROVADA' }).currentKey).toBe('aprovada');
    expect(propostaStatusToSteps({ status: 'CONVERTIDA' }).currentKey).toBe('pedido_venda');
  });

  it('marca como perigo quando rejeitada ou perdida, sem perder os steps', () => {
    const rejeitada = propostaStatusToSteps({ status: 'REJEITADA' });
    expect(rejeitada.currentKey).toBe('cotacao');
    expect(rejeitada.steps.find((s) => s.key === 'cotacao')?.tone).toBe('danger');
  });

  it('conversão parcial mantém pedido_venda como atual com tooltip próprio', () => {
    const parcial = propostaStatusToSteps({ status: 'PARCIALMENTE_CONVERTIDA' });
    expect(parcial.currentKey).toBe('pedido_venda');
    expect(parcial.steps.find((s) => s.key === 'pedido_venda')?.tooltip).toContain('parcial');
  });
});

describe('pedidoVendaStatusToSteps', () => {
  it('mapeia aberto → aprovado → em_faturamento → faturado', () => {
    expect(pedidoVendaStatusToSteps({ status: 'ABERTO' }).currentKey).toBe('aberto');
    expect(pedidoVendaStatusToSteps({ status: 'APROVADO' }).currentKey).toBe('aprovado');
    expect(pedidoVendaStatusToSteps({ status: 'EM_FATURAMENTO' }).currentKey).toBe('em_faturamento');
    expect(pedidoVendaStatusToSteps({ status: 'FATURADO' }).currentKey).toBe('faturado');
  });

  it('normaliza caixa e espaços do status vindo da API', () => {
    expect(pedidoVendaStatusToSteps({ status: ' aprovado ' }).currentKey).toBe('aprovado');
  });

  it('cancelado marca o step aberto como perigo', () => {
    const cancelado = pedidoVendaStatusToSteps({ status: 'CANCELADO' });
    expect(cancelado.currentKey).toBe('aberto');
    expect(cancelado.steps.find((s) => s.key === 'aberto')?.tone).toBe('danger');
  });

  it('faturamento parcial renomeia o step em_faturamento', () => {
    const parcial = pedidoVendaStatusToSteps({ status: 'PARCIALMENTE_FATURADO' });
    expect(parcial.currentKey).toBe('em_faturamento');
    expect(parcial.steps.find((s) => s.key === 'em_faturamento')?.label).toBe('Parcialmente Faturado');
  });
});

describe('nfeSaidaStatusToSteps', () => {
  it('usa o status da conferência quando a NF-e ainda não foi emitida', () => {
    expect(nfeSaidaStatusToSteps({ status: 'RASCUNHO' }).currentKey).toBe('rascunho');
    expect(
      nfeSaidaStatusToSteps({ status: 'RASCUNHO', status_conferencia: 'PRONTA_PARA_EMISSAO' })
        .currentKey,
    ).toBe('pronta');
  });

  it('autorizada e cancelada/ rejeitada têm destinos próprios', () => {
    expect(nfeSaidaStatusToSteps({ status: 'AUTORIZADA' }).currentKey).toBe('autorizada');
    expect(nfeSaidaStatusToSteps({ status: 'CANCELADA' }).currentKey).toBe('autorizada');
    expect(nfeSaidaStatusToSteps({ status: 'REJEITADA' }).currentKey).toBe('pronta');
  });

  it('cancelada e rejeitada marcam tom de perigo', () => {
    expect(
      nfeSaidaStatusToSteps({ status: 'CANCELADA' }).steps.find((s) => s.key === 'autorizada')?.tone,
    ).toBe('danger');
    expect(
      nfeSaidaStatusToSteps({ status: 'REJEITADA' }).steps.find((s) => s.key === 'pronta')?.tone,
    ).toBe('danger');
  });
});

describe('cotacaoStatusToSteps', () => {
  it('mapeia a progressão rascunho → em_cotacao → concluida', () => {
    expect(cotacaoStatusToSteps({ status: 'RASCUNHO' }).currentKey).toBe('rascunho');
    expect(cotacaoStatusToSteps({ status: 'EM_COTACAO' }).currentKey).toBe('em_cotacao');
    expect(cotacaoStatusToSteps({ status: 'CONCLUIDA' }).currentKey).toBe('concluida');
  });

  it('PARCIAL fica em em_cotacao com tooltip de respostas parciais', () => {
    const parcial = cotacaoStatusToSteps({ status: 'PARCIAL' });
    expect(parcial.currentKey).toBe('em_cotacao');
    expect(parcial.steps.find((s) => s.key === 'em_cotacao')?.tooltip).toContain('parciais');
  });

  it('CANCELADA marca em_cotacao como perigo', () => {
    const cancelada = cotacaoStatusToSteps({ status: 'CANCELADA' });
    expect(cancelada.currentKey).toBe('em_cotacao');
    expect(cancelada.steps.find((s) => s.key === 'em_cotacao')?.tone).toBe('danger');
  });

  it('status desconhecido ou vazio cai no primeiro step', () => {
    expect(cotacaoStatusToSteps({ status: null }).currentKey).toBe('rascunho');
    expect(cotacaoStatusToSteps({ status: 'INEXISTENTE' }).currentKey).toBe('rascunho');
  });

  it('expõe exatamente os três steps da cotação, em ordem', () => {
    expect(cotacaoStatusToSteps({ status: 'RASCUNHO' }).steps.map((s) => s.key)).toEqual([
      'rascunho',
      'em_cotacao',
      'concluida',
    ]);
  });
});

describe('pedidoCompraStatusToSteps', () => {
  it('mapeia Pendente → Aprovado → Recebido', () => {
    expect(pedidoCompraStatusToSteps({ status: 'Pendente' }).currentKey).toBe('pendente');
    expect(pedidoCompraStatusToSteps({ status: 'Aprovado' }).currentKey).toBe('aprovado');
    expect(pedidoCompraStatusToSteps({ status: 'Recebido' }).currentKey).toBe('recebido');
  });

  it('aceita as variantes em maiúsculas gravadas pelo backend', () => {
    expect(pedidoCompraStatusToSteps({ status: 'APROVADO' }).currentKey).toBe('aprovado');
    expect(pedidoCompraStatusToSteps({ status: 'APROVADA' }).currentKey).toBe('aprovado');
  });

  it('CANCELADO marca pendente como perigo', () => {
    const cancelado = pedidoCompraStatusToSteps({ status: 'CANCELADO' });
    expect(cancelado.currentKey).toBe('pendente');
    expect(cancelado.steps.find((s) => s.key === 'pendente')?.tone).toBe('danger');
  });

  it('sem status cai em pendente', () => {
    expect(pedidoCompraStatusToSteps({}).currentKey).toBe('pendente');
  });

  it('expõe exatamente os três steps do pedido de compra, em ordem', () => {
    expect(pedidoCompraStatusToSteps({ status: 'Pendente' }).steps.map((s) => s.key)).toEqual([
      'pendente',
      'aprovado',
      'recebido',
    ]);
  });
});

describe('nfeEntradaStatusToSteps', () => {
  it('mapeia rascunho → em_conferencia → pronta → autorizada', () => {
    expect(nfeEntradaStatusToSteps({ status_operacional: 'RASCUNHO' }).currentKey).toBe('rascunho');
    expect(nfeEntradaStatusToSteps({ status_operacional: 'EM_CONFERENCIA' }).currentKey).toBe(
      'em_conferencia',
    );
    expect(nfeEntradaStatusToSteps({ status_operacional: 'PRONTA_HOMOLOGACAO' }).currentKey).toBe(
      'pronta',
    );
    expect(
      nfeEntradaStatusToSteps({ status_operacional: 'AUTORIZADA_PRODUCAO' }).currentKey,
    ).toBe('autorizada');
  });

  it('IMPORTADA_PENDENTE_CONFERENCIA fica no rascunho com tooltip de importada', () => {
    const importada = nfeEntradaStatusToSteps({
      status_operacional: 'IMPORTADA_PENDENTE_CONFERENCIA',
    });
    expect(importada.currentKey).toBe('rascunho');
    expect(importada.steps.find((s) => s.key === 'rascunho')?.tooltip).toContain('Importada');
  });

  it('cancelada, inutilizada, rejeitada e erro de transmissão viram perigo', () => {
    const cancelada = nfeEntradaStatusToSteps({ status_operacional: 'CANCELADA_HOMOLOGACAO' });
    expect(cancelada.steps.find((s) => s.key === 'autorizada')?.tone).toBe('danger');

    const inutilizada = nfeEntradaStatusToSteps({ status_operacional: 'INUTILIZADA_PRODUCAO' });
    expect(inutilizada.steps.find((s) => s.key === 'rascunho')?.tone).toBe('danger');

    const rejeitada = nfeEntradaStatusToSteps({ status_operacional: 'REJEITADA' });
    expect(rejeitada.steps.find((s) => s.key === 'pronta')?.tone).toBe('danger');

    const erro = nfeEntradaStatusToSteps({ status_operacional: 'ERRO_TRANSMISSAO' });
    expect(erro.steps.find((s) => s.key === 'pronta')?.tone).toBe('danger');
  });

  it('status vazio ou desconhecido cai no rascunho', () => {
    expect(nfeEntradaStatusToSteps({}).currentKey).toBe('rascunho');
    expect(nfeEntradaStatusToSteps({ status_operacional: 'NADA_A_VER' }).currentKey).toBe('rascunho');
  });

  it('expõe exatamente os quatro steps da entrada, em ordem', () => {
    expect(nfeEntradaStatusToSteps({}).steps.map((s) => s.key)).toEqual([
      'rascunho',
      'em_conferencia',
      'pronta',
      'autorizada',
    ]);
  });
});
