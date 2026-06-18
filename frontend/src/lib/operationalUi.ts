/**
 * ERP 4.0.13.8 — Camada operacional de linguagem, status e mensagens amigáveis.
 * Tela principal = negócio; detalhes técnicos ficam em Avançado / Suporte técnico.
 */

/** Rótulos de ações padronizados (verbos operacionais). */
export const ACTION_LABELS = {
  salvarAlteracoes: 'Salvar alterações',
  validarDados: 'Validar dados',
  validarDadosSalvos: 'Validar dados',
  salvarEValidar: 'Salvar e validar',
  verDanfe: 'Ver DANFE',
  emitirNfe: 'Emitir NF-e',
  reenviarNfe: 'Reenviar NF-e',
  prepararEmissao: 'Preparar emissão',
  descartarRascunho: 'Descartar rascunho',
  baixarXml: 'Baixar XML',
  cancelarNfe: 'Cancelar NF-e',
  enviarDanfeXml: 'Enviar DANFE/XML',
  cartaCorrecao: 'Carta de Correção',
  historicoSefaz: 'Histórico SEFAZ',
  corrigirDados: 'Corrigir dados',
  validarNovamente: 'Validar novamente',
  confirmarVinculo: 'Confirmar vínculo',
  rejeitarSugestao: 'Rejeitar sugestão',
  ajustarVinculo: 'Ajustar vínculo',
} as const;

/** Status NF-e — linguagem de negócio na UI principal. */
export const NFE_STATUS_LABELS: Record<string, string> = {
  RASCUNHO: 'Rascunho',
  EM_CONFERENCIA: 'Em conferência',
  PRONTA_PARA_EMISSAO: 'Pronta para emissão',
  AUTORIZADA_HOMOLOGACAO: 'NF-e autorizada',
  AUTORIZADA: 'NF-e autorizada',
  REJEITADA_HOMOLOGACAO: 'NF-e rejeitada',
  ERRO_TRANSMISSAO: 'Erro na transmissão',
  CANCELADA: 'NF-e cancelada',
  DENEGADA: 'NF-e denegada',
  XML_GERADO: 'XML gerado',
  XML_ASSINADO: 'XML assinado',
};

export function labelNfeStatusOperacional(status: string | null | undefined): string {
  const key = (status || '').trim().toUpperCase();
  if (!key) return 'Em conferência';
  return NFE_STATUS_LABELS[key] ?? status ?? 'Em conferência';
}

/** Status operacional na conferência — prioriza SEFAZ; senão usa status_conferencia. */
export function labelNfeStatusConferenciaOperacional(
  statusEmissaoSefaz: string | null | undefined,
  statusConferencia: string | null | undefined,
): string {
  const sefaz = (statusEmissaoSefaz || '').trim();
  if (sefaz) return labelNfeStatusOperacional(sefaz);
  return labelNfeStatusOperacional(statusConferencia || 'EM_CONFERENCIA');
}

/** Status pedido de venda. */
export const PEDIDO_STATUS_LABELS: Record<string, string> = {
  ABERTO: 'Aberto',
  APROVADO: 'Aprovado',
  EM_FATURAMENTO: 'Pendente de faturamento',
  PARCIALMENTE_FATURADO: 'Parcialmente faturado',
  FATURADO: 'Faturado',
  CANCELADO: 'Cancelado',
};

export function labelPedidoStatusOperacional(status: string): string {
  return PEDIDO_STATUS_LABELS[status] ?? status;
}

/** Status proposta. */
export const PROPOSTA_STATUS_LABELS: Record<string, string> = {
  RASCUNHO: 'Rascunho',
  PENDENTE: 'Rascunho',
  ENVIADA: 'Enviada',
  APROVADA: 'Aprovada',
  CONVERTIDA: 'Convertida em pedido',
  PARCIALMENTE_CONVERTIDA: 'Parcialmente convertida',
  REABERTA: 'Reaberta / em negociação',
  PERDIDA: 'Perdida',
  PERDIDO: 'Perdida',
  RECUSADA: 'Recusada',
  CANCELADA: 'Cancelada',
};

export function labelPropostaStatusOperacional(status: string): string {
  return PROPOSTA_STATUS_LABELS[status] ?? status;
}

/** Produtos / famílias. */
export const PRODUTO_UI_LABELS = {
  tipoDimensional: 'Modelo de medidas',
  regraCodigo: 'Como o código será formado',
  camposExigidos: 'Campos que o produto vai pedir',
  sugestaoModelo: 'Pelo texto digitado, o sistema sugere este modelo de medidas.',
  composicaoMontagem: 'Composição / Montagem',
  produtoFinal: 'Produto final',
  componentes: 'Componentes',
  tipoMontagem: 'Tipo de montagem',
} as const;

/** NF-e entrada / compras. */
export const ENTRADA_UI_LABELS = {
  itensAgrupados: 'Itens do fornecedor agrupados',
  vinculoProduto: 'Vínculo com produto cadastrado',
  sugestaoSistema: 'Sugestão do sistema',
  avisoVinculo:
    'Confirmar vínculo não movimenta estoque nem gera financeiro.',
} as const;

/** Rótulos técnicos → operacionais (XML/DANFE na área principal). */
export const TECHNICAL_DOWNLOAD_LABELS = {
  xmlPreliminar: 'XML preliminar 4.00',
  xmlOficial: 'XML oficial 4.00',
  xmlAssinado: 'XML assinado',
  xmlLote: 'XML lote enviado',
  xmlRetorno: 'XML retorno SEFAZ',
  xmlAutorizado: 'XML autorizado',
  previewXml: 'Prévia XML',
  validarXmlLocal: 'Validar XML localmente',
  gerarXmlTransmissao: 'Gerar XML transmissão',
} as const;

const FRIENDLY_PATTERNS: Array<{ test: RegExp; message: string }> = [
  {
    test: /snapshot_fiscal|snapshot fiscal/i,
    message:
      'Os dados fiscais deste item ainda não foram calculados. Clique em Atualizar fiscal e valide novamente.',
  },
  {
    test: /chave.*inv[aá]lida|xml.*transmiss[aã]o.*chave/i,
    message: 'Não foi possível preparar a NF-e para emissão. Valide os dados antes de emitir.',
  },
  {
    test: /validação xsd|validacao xsd|schema xml/i,
    message: 'Não foi possível preparar a NF-e para emissão. Valide os dados antes de emitir.',
  },
  {
    test: /bfr|renderer|weasyprint|fallback html/i,
    message: 'Não foi possível gerar o DANFE. A nota não foi alterada. Tente novamente ou acione o suporte.',
  },
  {
    test: /receitaws|payload|cnpj.*api/i,
    message: 'Não foi possível consultar o CNPJ agora. Você pode preencher os dados manualmente.',
  },
  {
    test: /validationerror|typeerror|attributeerror/i,
    message: 'Não foi possível concluir a operação. Verifique os dados e tente novamente.',
  },
];

/** Converte mensagem técnica em linguagem operacional para a área principal. */
export function friendlyOperationalMessage(
  raw: string | null | undefined,
  fallback = 'Não foi possível concluir a operação. Tente novamente.',
): string {
  const text = (raw || '').trim();
  if (!text) return fallback;
  for (const { test, message } of FRIENDLY_PATTERNS) {
    if (test.test(text)) return message;
  }
  return text;
}

/** Mensagem orientativa por status NF-e na conferência. */
export function mensagemOrientacaoNfeConferencia(opts: {
  autorizada: boolean;
  rejeitada: boolean;
  cancelada: boolean;
  pronta: boolean;
}): string {
  if (opts.autorizada) return 'NF-e autorizada pela SEFAZ.';
  if (opts.cancelada) return 'NF-e cancelada. Consulte o histórico para detalhes.';
  if (opts.rejeitada) return 'NF-e rejeitada pela SEFAZ. Corrija os dados e reenvie.';
  if (opts.pronta) return 'Dados validados. Você pode emitir a NF-e.';
  return 'Revise os dados da NF-e antes de emitir.';
}

/** Sugestão de nível de confiança (equivalência entrada). */
export function labelNivelSugestao(nivel: string): string {
  const n = (nivel || '').toLowerCase();
  if (n === 'alta') return 'Alta';
  if (n === 'media') return 'Média';
  if (n === 'baixa') return 'Baixa';
  return nivel || '—';
}
