import type { StatusStep } from '@/components/layout/StatusPipeline';

export interface StatusPipelineState {
  steps: StatusStep[];
  currentKey: string;
}

function normStatus(status: string | null | undefined): string {
  return (status || '').trim().toUpperCase();
}

function withCancelledStep(base: StatusStep[], key: string, tooltip: string): StatusPipelineState {
  return {
    steps: base.map((step) =>
      step.key === key ? { ...step, tone: 'danger' as const, tooltip } : step,
    ),
    currentKey: key,
  };
}

const PROPOSTA_BASE: StatusStep[] = [
  { key: 'cotacao', label: 'Cotação', tooltip: 'Proposta criada, aguardando decisão do cliente' },
  { key: 'aprovada', label: 'Aprovada', tooltip: 'Proposta aprovada internamente' },
  { key: 'pedido_venda', label: 'Pedido de Venda', tooltip: 'Proposta convertida em pedido de venda' },
];

export function propostaStatusToSteps(proposta: {
  status?: string | null;
}): StatusPipelineState {
  const st = normStatus(proposta.status);

  if (st === 'CANCELADA' || st === 'CANCELADO' || st === 'PERDIDA' || st === 'PERDIDO') {
    return withCancelledStep(PROPOSTA_BASE, 'cotacao', `Proposta ${st.toLowerCase()}`);
  }
  if (st === 'REJEITADA' || st === 'REJEITADO') {
    return withCancelledStep(PROPOSTA_BASE, 'cotacao', 'Proposta rejeitada');
  }
  if (st === 'APROVADA' || st === 'APROVADO') {
    return { steps: PROPOSTA_BASE, currentKey: 'aprovada' };
  }
  if (st === 'CONVERTIDA') {
    return { steps: PROPOSTA_BASE, currentKey: 'pedido_venda' };
  }
  if (st === 'PARCIALMENTE_CONVERTIDA') {
    return {
      steps: PROPOSTA_BASE.map((step) =>
        step.key === 'pedido_venda'
          ? { ...step, tooltip: 'Conversão parcial: apenas alguns itens viraram pedido' }
          : step,
      ),
      currentKey: 'pedido_venda',
    };
  }
  return { steps: PROPOSTA_BASE, currentKey: 'cotacao' };
}

const PEDIDO_VENDA_BASE: StatusStep[] = [
  { key: 'aberto', label: 'Aberto', tooltip: 'Pedido criado, aguardando aprovação' },
  { key: 'aprovado', label: 'Aprovado', tooltip: 'Pedido aprovado para faturamento' },
  { key: 'em_faturamento', label: 'Em Faturamento', tooltip: 'Faturamento em andamento' },
  { key: 'faturado', label: 'Faturado', tooltip: 'Pedido totalmente faturado' },
];

export function pedidoVendaStatusToSteps(pedido: {
  status?: string | null;
}): StatusPipelineState {
  const st = normStatus(pedido.status);

  if (st === 'CANCELADO' || st === 'CANCELADA') {
    return withCancelledStep(PEDIDO_VENDA_BASE, 'aberto', 'Pedido cancelado');
  }
  if (st === 'APROVADO') {
    return { steps: PEDIDO_VENDA_BASE, currentKey: 'aprovado' };
  }
  if (st === 'EM_FATURAMENTO') {
    return { steps: PEDIDO_VENDA_BASE, currentKey: 'em_faturamento' };
  }
  if (st === 'PARCIALMENTE_FATURADO' || st === 'PARCIAL') {
    return {
      steps: PEDIDO_VENDA_BASE.map((step) =>
        step.key === 'em_faturamento'
          ? { ...step, label: 'Parcialmente Faturado', tooltip: 'Faturamento parcial do pedido' }
          : step,
      ),
      currentKey: 'em_faturamento',
    };
  }
  if (st === 'FATURADO') {
    return { steps: PEDIDO_VENDA_BASE, currentKey: 'faturado' };
  }
  return { steps: PEDIDO_VENDA_BASE, currentKey: 'aberto' };
}

const NFE_SAIDA_BASE: StatusStep[] = [
  { key: 'rascunho', label: 'Rascunho', tooltip: 'NF-e em digitação/conferência interna' },
  { key: 'pronta', label: 'Pronta', tooltip: 'Conferência finalizada, pronta para emissão' },
  { key: 'autorizada', label: 'Autorizada', tooltip: 'NF-e autorizada pela SEFAZ' },
];

export function nfeSaidaStatusToSteps(nfe: {
  status?: string | null;
  status_conferencia?: string | null;
}): StatusPipelineState {
  const st = normStatus(nfe.status);
  const conferencia = normStatus(nfe.status_conferencia);

  if (st.includes('CANCEL')) {
    return withCancelledStep(NFE_SAIDA_BASE, 'autorizada', 'NF-e cancelada');
  }
  if (st.includes('REJEIT')) {
    return withCancelledStep(NFE_SAIDA_BASE, 'pronta', 'Emissão rejeitada pela SEFAZ');
  }
  if (st === 'DESCARTADA_INTERNA') {
    return withCancelledStep(NFE_SAIDA_BASE, 'rascunho', 'Rascunho descartado internamente');
  }
  if (st === 'AUTORIZADA' || st.startsWith('AUTORIZADA_') || st === 'EMITIDA' || st === 'EMITIDO') {
    return { steps: NFE_SAIDA_BASE, currentKey: 'autorizada' };
  }
  if (st === 'PRONTA' || conferencia === 'PRONTA_PARA_EMISSAO') {
    return { steps: NFE_SAIDA_BASE, currentKey: 'pronta' };
  }
  return { steps: NFE_SAIDA_BASE, currentKey: 'rascunho' };
}

const COTACAO_BASE: StatusStep[] = [
  { key: 'rascunho', label: 'Rascunho', tooltip: 'Cotação criada, ainda não enviada aos fornecedores' },
  { key: 'em_cotacao', label: 'Em cotação', tooltip: 'Fornecedores convidados, aguardando respostas' },
  { key: 'concluida', label: 'Concluída', tooltip: 'Respostas recebidas e cotação encerrada' },
];

export function cotacaoStatusToSteps(cotacao: {
  status?: string | null;
}): StatusPipelineState {
  const st = normStatus(cotacao.status);

  if (st === 'CANCELADA' || st === 'CANCELADO') {
    return withCancelledStep(COTACAO_BASE, 'em_cotacao', 'Cotação cancelada');
  }
  if (st === 'CONCLUIDA' || st === 'CONCLUIDO') {
    return { steps: COTACAO_BASE, currentKey: 'concluida' };
  }
  if (st === 'PARCIAL') {
    return {
      steps: COTACAO_BASE.map((step) =>
        step.key === 'em_cotacao'
          ? { ...step, tooltip: 'Respostas parciais: nem todos os itens foram cotados' }
          : step,
      ),
      currentKey: 'em_cotacao',
    };
  }
  if (st === 'EM_COTACAO') {
    return { steps: COTACAO_BASE, currentKey: 'em_cotacao' };
  }
  return { steps: COTACAO_BASE, currentKey: 'rascunho' };
}

const PEDIDO_COMPRA_BASE: StatusStep[] = [
  { key: 'pendente', label: 'Pendente', tooltip: 'Pedido criado, aguardando aprovação' },
  { key: 'aprovado', label: 'Aprovado', tooltip: 'Pedido aprovado para compra' },
  { key: 'recebido', label: 'Recebido', tooltip: 'Mercadoria recebida' },
];

export function pedidoCompraStatusToSteps(pedido: {
  status?: string | null;
}): StatusPipelineState {
  const st = normStatus(pedido.status);

  if (st === 'CANCELADO' || st === 'CANCELADA') {
    return withCancelledStep(PEDIDO_COMPRA_BASE, 'pendente', 'Pedido cancelado');
  }
  if (st === 'RECEBIDO' || st === 'RECEBIDA' || st === 'CONCLUIDO' || st === 'CONCLUIDA') {
    return { steps: PEDIDO_COMPRA_BASE, currentKey: 'recebido' };
  }
  if (st === 'APROVADO' || st === 'APROVADA') {
    return { steps: PEDIDO_COMPRA_BASE, currentKey: 'aprovado' };
  }
  return { steps: PEDIDO_COMPRA_BASE, currentKey: 'pendente' };
}

const NFE_ENTRADA_BASE: StatusStep[] = [
  { key: 'rascunho', label: 'Rascunho', tooltip: 'NF-e de entrada em digitação/conferência interna' },
  { key: 'em_conferencia', label: 'Em Conferência', tooltip: 'Conferência de itens em andamento' },
  { key: 'pronta', label: 'Pronta', tooltip: 'Conferência finalizada, pronta para emissão' },
  { key: 'autorizada', label: 'Autorizada', tooltip: 'NF-e autorizada pela SEFAZ' },
];

export function nfeEntradaStatusToSteps(nfe: {
  status_operacional?: string | null;
}): StatusPipelineState {
  const st = normStatus(nfe.status_operacional);

  if (st.startsWith('CANCELADA_') || st.startsWith('CANCELADO_')) {
    return withCancelledStep(NFE_ENTRADA_BASE, 'autorizada', 'NF-e cancelada');
  }
  if (st.startsWith('INUTILIZADA_')) {
    return withCancelledStep(NFE_ENTRADA_BASE, 'rascunho', 'Numeração inutilizada');
  }
  if (st === 'REJEITADA') {
    return withCancelledStep(NFE_ENTRADA_BASE, 'pronta', 'Emissão rejeitada pela SEFAZ');
  }
  if (st === 'ERRO_TRANSMISSAO') {
    return withCancelledStep(NFE_ENTRADA_BASE, 'pronta', 'Falha na transmissão para a SEFAZ');
  }
  if (st.startsWith('AUTORIZADA_')) {
    return { steps: NFE_ENTRADA_BASE, currentKey: 'autorizada' };
  }
  if (st.startsWith('PRONTA_')) {
    return { steps: NFE_ENTRADA_BASE, currentKey: 'pronta' };
  }
  if (st === 'EM_CONFERENCIA') {
    return { steps: NFE_ENTRADA_BASE, currentKey: 'em_conferencia' };
  }
  if (st === 'IMPORTADA_PENDENTE_CONFERENCIA') {
    return {
      steps: NFE_ENTRADA_BASE.map((step) =>
        step.key === 'rascunho'
          ? { ...step, tooltip: 'Importada: ainda pendente de conferência' }
          : step,
      ),
      currentKey: 'rascunho',
    };
  }
  return { steps: NFE_ENTRADA_BASE, currentKey: 'rascunho' };
}
