/**
 * ERP 4.0.14 — Linguagem operacional do Financeiro.
 */

import { formatMoneyBRL } from '@/lib/money';

export const FINANCEIRO_STATUS_LABELS: Record<string, string> = {
  EM_ABERTO: 'Em aberto',
  VENCIDO: 'Vencido',
  PARCIALMENTE_RECEBIDO: 'Parcialmente recebido',
  RECEBIDO: 'Recebido',
  PARCIALMENTE_PAGO: 'Parcialmente pago',
  PAGO: 'Pago',
  CANCELADO: 'Cancelado',
  ESTORNADO: 'Estornado',
};

export function labelStatusFinanceiro(status: string | null | undefined, statusLabel?: string): string {
  if (statusLabel?.trim()) return statusLabel.trim();
  const key = (status || '').trim().toUpperCase();
  return FINANCEIRO_STATUS_LABELS[key] ?? status ?? '—';
}

/** Status para StatusBadge — prioriza rótulo amigável da API. */
export function statusBadgeFinanceiro(titulo: { status: string; status_label?: string }): string {
  return labelStatusFinanceiro(titulo.status, titulo.status_label);
}

export const TIPO_LANCAMENTO_PAGAR_LABELS: Record<string, string> = {
  FORNECEDOR: 'Fornecedor',
  DESPESA_OPERACIONAL: 'Despesa operacional',
  SERVICO: 'Serviço',
  TRIBUTO_IMPOSTO: 'Tributo / Imposto',
  OUTROS: 'Outros',
};

export const TIPO_TRIBUTO_LABELS: Record<string, string> = {
  ICMS: 'ICMS',
  PIS: 'PIS',
  COFINS: 'COFINS',
  IPI: 'IPI',
  ISS: 'ISS',
  IBS: 'IBS',
  CBS: 'CBS',
  IR: 'IR',
  CSLL: 'CSLL',
  INSS: 'INSS',
  FGTS: 'FGTS',
  OUTROS: 'Outros',
};

export function labelTipoLancamentoPagar(tipo: string | null | undefined, label?: string): string {
  if (label?.trim()) return label.trim();
  const key = (tipo || '').trim().toUpperCase();
  return TIPO_LANCAMENTO_PAGAR_LABELS[key] ?? tipo ?? '—';
}

export function labelTipoTributo(tipo: string | null | undefined, label?: string): string {
  if (label?.trim()) return label.trim();
  const key = (tipo || '').trim().toUpperCase();
  return TIPO_TRIBUTO_LABELS[key] ?? tipo ?? '—';
}

export const FINANCEIRO_ACTION_LABELS = {
  novaContaReceber: 'Nova conta a receber',
  novaContaPagar: 'Nova conta a pagar',
  novaDespesa: 'Nova despesa',
  novoTributo: 'Novo tributo a pagar',
  parcelar: 'Parcelar',
  parcelarTitulo: 'Parcelar este título',
  baixarRecebimento: 'Baixar recebimento',
  baixarPagamento: 'Baixar pagamento',
  baixarSaldoRestante: 'Baixar saldo restante',
  estornarBaixa: 'Estornar baixa',
  cancelarTitulo: 'Cancelar título',
  verDetalhes: 'Ver detalhes',
  editar: 'Editar',
  aplicarCredito: 'Aplicar crédito',
  aplicarCreditoFornecedor: 'Aplicar crédito do fornecedor',
  abaterDevolucao: 'Abater por devolução',
  verHistorico: 'Ver histórico',
  novoCreditoCliente: 'Novo crédito de cliente',
  novoCreditoFornecedor: 'Novo crédito de fornecedor',
  novoCredito: 'Novo crédito',
  editarCredito: 'Editar crédito',
  excluirCredito: 'Excluir crédito',
  excluirTitulo: 'Excluir título',
  estornarUsoCredito: 'Estornar uso de crédito',
  estornarAbatimento: 'Estornar abatimento',
  cancelarCredito: 'Cancelar crédito',
} as const;

export const FINANCEIRO_OPERATIONAL_MESSAGES = {
  tituloEmAbertoReceber:
    'Título em aberto. Você pode registrar recebimento, editar dados ou cancelar o título.',
  tituloEmAbertoPagar:
    'Título em aberto. Você pode registrar pagamento, editar dados ou cancelar o título.',
  parcialRecebido: 'Este título possui recebimento parcial. Ainda há saldo em aberto.',
  parcialPago: 'Este título possui pagamento parcial. Ainda há saldo em aberto.',
  recebidoEstorno: 'Este título já foi recebido. Para alterar valores, estorne a baixa primeiro.',
  pagoEstorno: 'Este título já foi pago. Para alterar valores, estorne a baixa primeiro.',
  cancelado: 'Este título foi cancelado e não aceita novas baixas.',
  vencidoReceber:
    'Este título está vencido. Você ainda pode registrar recebimento, cancelar ou ajustar conforme permissão.',
  vencidoPagar:
    'Este título está vencido. Você ainda pode registrar pagamento, cancelar ou ajustar conforme permissão.',
  creditoAplicado: 'Este título possui crédito aplicado.',
  abatimentoRegistrado: 'Este título possui abatimento registrado.',
} as const;

export const FINANCEIRO_MESSAGES = {
  /** @deprecated Use FINANCEIRO_OPERATIONAL_MESSAGES.recebidoEstorno / pagoEstorno */
  tituloBaixado:
    'Este título já foi baixado. Para alterar valores, estorne a baixa primeiro.',
  tituloVencido: 'Este título está vencido.',
  erroSalvarTitulo:
    'Não foi possível salvar o título. Verifique cliente, vencimento e valor.',
  erroSalvarPagar:
    'Não foi possível salvar o título. Verifique fornecedor, vencimento e valor.',
} as const;

export type TituloModo = 'RECEBER' | 'PAGAR';

export function tituloModoConfig(modo: TituloModo) {
  if (modo === 'RECEBER') {
    return {
      tituloPagina: 'Contas a Receber',
      descricao: 'Títulos a receber de clientes — baixas, vencimentos e origem rastreável.',
      contraparteLabel: 'Cliente',
      valorPagoLabel: 'Valor recebido',
      saldoLabel: 'Saldo em aberto',
      baixarLabel: FINANCEIRO_ACTION_LABELS.baixarRecebimento,
      novoLabel: FINANCEIRO_ACTION_LABELS.novaContaReceber,
      erroSalvar: FINANCEIRO_MESSAGES.erroSalvarTitulo,
    };
  }
  return {
    tituloPagina: 'Contas a Pagar',
    descricao: 'Títulos a pagar para fornecedores — baixas, vencimentos e origem rastreável.',
    contraparteLabel: 'Fornecedor',
    valorPagoLabel: 'Valor pago',
    saldoLabel: 'Saldo em aberto',
    baixarLabel: FINANCEIRO_ACTION_LABELS.baixarPagamento,
    novoLabel: FINANCEIRO_ACTION_LABELS.novaContaPagar,
    erroSalvar: FINANCEIRO_MESSAGES.erroSalvarPagar,
  };
}

export const FORMA_PAGAMENTO_FIXA_LABELS: Record<string, string> = {
  PIX: 'Pix',
  BOLETO: 'Boleto',
  TRANSFERENCIA_BANCARIA: 'Transferência bancária',
  DINHEIRO: 'Dinheiro',
  CARTAO_CREDITO: 'Cartão de crédito',
  CARTAO_DEBITO: 'Cartão de débito',
  CHEQUE: 'Cheque',
  DEPOSITO_BANCARIO: 'Depósito bancário',
  SEM_MOVIMENTACAO_FINANCEIRA: 'Sem movimentação financeira',
  OUTROS: 'Outros',
};

export function contaFinanceiraTipoBanco(tipo: string | null | undefined): boolean {
  return (tipo || '').trim().toUpperCase() === 'BANCO';
}

/** Coluna Banco na listagem de contas / caixas. */
export function labelBancoContaListagem(conta: { tipo: string; banco?: string | null }): string {
  if (!contaFinanceiraTipoBanco(conta.tipo)) return '—';
  const banco = (conta.banco || '').trim();
  return banco || 'Não informado';
}

export type ContaFinanceiraFormValues = {
  nome: string;
  tipo: string;
  banco: string;
  agencia: string;
  conta: string;
  ativo: boolean;
  observacoes: string;
};

/** Label do campo nome no modal Conta/Caixa — evita duplicidade com instituição bancária. */
export function labelNomeContaFinanceira(tipo: string | null | undefined): string {
  return contaFinanceiraTipoBanco(tipo) ? 'Descrição / Apelido da conta' : 'Nome da conta/caixa';
}

export function placeholderNomeContaFinanceira(tipo: string | null | undefined): string {
  if (contaFinanceiraTipoBanco(tipo)) {
    return 'Ex.: Conta principal, Conta movimento, Conta recebimentos';
  }
  return 'Ex.: Caixa interno, Carteira Pix, Cofre, Conta operacional';
}

export const PLACEHOLDER_BANCO_CONTA_FINANCEIRA =
  'Ex.: Itaú, Bradesco, Banco do Brasil, Santander, Caixa';

export const PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO =
  'Buscar fornecedor por razão social, nome fantasia ou CNPJ...';

export const PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO =
  'Buscar cliente por razão social, nome fantasia, CNPJ ou CPF...';

export const FINANCEIRO_FORNECEDOR_MESSAGES = {
  selecioneFornecedor: 'Selecione um fornecedor.',
  despesaFornecedorOpcional: 'Informe um fornecedor se esta despesa estiver vinculada a alguém.',
  semFornecedor: 'Sem fornecedor',
} as const;

export const FINANCEIRO_CLIENTE_MESSAGES = {
  selecioneCliente: 'Selecione um cliente.',
  informeVencimento: 'Informe o vencimento.',
  informeValorMaiorZero: 'Informe um valor maior que zero.',
} as const;

export type ContaReceberFormValues = {
  data_emissao: string;
  data_vencimento: string;
  valor_original: string;
};

/** Validação mínima do cadastro manual de conta a receber. */
export function validarContaReceberForm(
  selectedClienteId: number | null,
  form: ContaReceberFormValues,
): string | null {
  if (!selectedClienteId) return FINANCEIRO_CLIENTE_MESSAGES.selecioneCliente;
  if (!(form.data_vencimento || '').trim()) return FINANCEIRO_CLIENTE_MESSAGES.informeVencimento;
  const valor = Number(String(form.valor_original).replace(',', '.'));
  if (!Number.isFinite(valor) || valor <= 0) return FINANCEIRO_CLIENTE_MESSAGES.informeValorMaiorZero;
  return null;
}

/** Validação mínima do cadastro de conta — banco obrigatório quando tipo = Banco. */
export function validarContaFinanceiraForm(form: ContaFinanceiraFormValues): string | null {
  if (!(form.nome || '').trim()) {
    return contaFinanceiraTipoBanco(form.tipo)
      ? 'Informe uma descrição para identificar esta conta.'
      : 'Informe o nome da conta.';
  }
  if (contaFinanceiraTipoBanco(form.tipo) && !(form.banco || '').trim()) {
    return 'Informe o banco para contas do tipo Banco.';
  }
  return null;
}

const FINANCEIRO_CENTAVO = 0.01;

export type TituloFinanceiroOperacional = {
  status: string;
  status_label?: string;
  cancelado?: boolean;
  valor_aberto?: string | number;
  valor_baixado?: string | number;
  data_vencimento?: string;
  pode_editar?: boolean;
  pode_baixar?: boolean;
  pode_cancelar?: boolean;
  possui_baixa_ativa?: boolean;
  pode_estornar_baixa?: boolean;
  pode_abater?: boolean;
  pode_aplicar_credito?: boolean;
  possui_credito_aplicado?: boolean;
  possui_abatimento?: boolean;
  pode_excluir?: boolean;
  origem_manual?: boolean;
  possui_movimento_financeiro?: boolean;
  possui_movimento_financeiro_ativo?: boolean;
  possui_apenas_movimentos_estornados?: boolean;
  possui_vinculo_origem?: boolean;
  motivo_bloqueio_exclusao?: string;
  saldo_integral_reaberto?: boolean;
  eventos?: unknown[];
};

export function parseValorFinanceiro(val: string | number | null | undefined): number {
  if (typeof val === 'number') return val;
  const n = Number(String(val ?? '0').replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

function hojeIsoLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function resolveTituloFinanceiroFlags(titulo: TituloFinanceiroOperacional) {
  const valorAberto = parseValorFinanceiro(titulo.valor_aberto);
  const valorBaixado = parseValorFinanceiro(titulo.valor_baixado);
  const cancelado = Boolean(titulo.cancelado || titulo.status === 'CANCELADO');
  const podeBaixar = titulo.pode_baixar ?? (!cancelado && valorAberto > FINANCEIRO_CENTAVO);
  const podeEditar = titulo.pode_editar ?? (!cancelado && valorBaixado <= FINANCEIRO_CENTAVO);
  const podeCancelar = titulo.pode_cancelar ?? podeEditar;
  const possuiBaixaAtiva = titulo.possui_baixa_ativa ?? valorBaixado > FINANCEIRO_CENTAVO;
  return {
    pode_baixar: podeBaixar,
    pode_editar: podeEditar,
    pode_cancelar: podeCancelar,
    possui_baixa_ativa: possuiBaixaAtiva,
    pode_estornar_baixa: titulo.pode_estornar_baixa ?? (possuiBaixaAtiva && !cancelado),
    pode_abater: titulo.pode_abater ?? podeBaixar,
    pode_aplicar_credito: titulo.pode_aplicar_credito ?? podeBaixar,
    possui_credito_aplicado: Boolean(titulo.possui_credito_aplicado),
    possui_abatimento: Boolean(titulo.possui_abatimento),
    pode_excluir: titulo.pode_excluir ?? false,
    motivo_bloqueio_exclusao: titulo.motivo_bloqueio_exclusao ?? '',
    possui_movimento_financeiro_ativo: titulo.possui_movimento_financeiro_ativo ?? false,
    possui_apenas_movimentos_estornados: titulo.possui_apenas_movimentos_estornados ?? false,
  };
}

export type TituloFinanceiroOperationalMessageTone = 'default' | 'warning' | 'muted';

export function getTituloFinanceiroOperationalMessages(
  titulo: TituloFinanceiroOperacional,
  modo: TituloModo,
): { messages: string[]; tone: TituloFinanceiroOperationalMessageTone } {
  const flags = resolveTituloFinanceiroFlags(titulo);
  const valorAberto = parseValorFinanceiro(titulo.valor_aberto);
  const valorBaixado = parseValorFinanceiro(titulo.valor_baixado);
  const status = (titulo.status || '').trim().toUpperCase();
  const messages: string[] = [];
  let tone: TituloFinanceiroOperationalMessageTone = 'default';

  if (titulo.cancelado || status === 'CANCELADO') {
    return { messages: [FINANCEIRO_OPERATIONAL_MESSAGES.cancelado], tone: 'muted' };
  }

  const quitado =
    status === 'RECEBIDO' || status === 'PAGO' || (valorAberto <= FINANCEIRO_CENTAVO && valorBaixado > FINANCEIRO_CENTAVO);
  const parcial = status === 'PARCIALMENTE_RECEBIDO' || status === 'PARCIALMENTE_PAGO';
  const emAberto =
    status === 'EM_ABERTO' || (valorAberto > FINANCEIRO_CENTAVO && valorBaixado <= FINANCEIRO_CENTAVO && !parcial);

  if (quitado && flags.possui_baixa_ativa) {
    messages.push(
      modo === 'RECEBER'
        ? FINANCEIRO_OPERATIONAL_MESSAGES.recebidoEstorno
        : FINANCEIRO_OPERATIONAL_MESSAGES.pagoEstorno,
    );
    tone = 'muted';
  } else if (parcial && valorAberto > FINANCEIRO_CENTAVO) {
    messages.push(
      modo === 'RECEBER'
        ? FINANCEIRO_OPERATIONAL_MESSAGES.parcialRecebido
        : FINANCEIRO_OPERATIONAL_MESSAGES.parcialPago,
    );
  } else if (emAberto) {
    messages.push(
      modo === 'RECEBER'
        ? FINANCEIRO_OPERATIONAL_MESSAGES.tituloEmAbertoReceber
        : FINANCEIRO_OPERATIONAL_MESSAGES.tituloEmAbertoPagar,
    );
  }

  const vencido =
    status === 'VENCIDO' ||
    (valorAberto > FINANCEIRO_CENTAVO &&
      Boolean(titulo.data_vencimento) &&
      titulo.data_vencimento! < hojeIsoLocal());
  if (vencido && !quitado) {
    messages.push(
      modo === 'RECEBER'
        ? FINANCEIRO_OPERATIONAL_MESSAGES.vencidoReceber
        : FINANCEIRO_OPERATIONAL_MESSAGES.vencidoPagar,
    );
    if (tone === 'default') tone = 'warning';
  }

  if (flags.possui_credito_aplicado) {
    messages.push(FINANCEIRO_OPERATIONAL_MESSAGES.creditoAplicado);
  }
  if (flags.possui_abatimento) {
    messages.push(FINANCEIRO_OPERATIONAL_MESSAGES.abatimentoRegistrado);
  }

  return { messages, tone };
}

export type TituloFinanceiroAcaoId =
  | 'baixar'
  | 'editar'
  | 'excluir'
  | 'cancelar'
  | 'estornar_baixa'
  | 'aplicar_credito'
  | 'abater_devolucao'
  | 'ver_historico';

export type TituloFinanceiroAcao = {
  id: TituloFinanceiroAcaoId;
  label: string;
  variant?: 'primary' | 'outline' | 'destructive';
};

export function getTituloFinanceiroAcoes(
  titulo: TituloFinanceiroOperacional,
  modo: TituloModo,
): TituloFinanceiroAcao[] {
  const flags = resolveTituloFinanceiroFlags(titulo);
  const status = (titulo.status || '').trim().toUpperCase();
  const cancelado = Boolean(titulo.cancelado || status === 'CANCELADO');
  const parcial = status === 'PARCIALMENTE_RECEBIDO' || status === 'PARCIALMENTE_PAGO';
  const quitado = status === 'RECEBIDO' || status === 'PAGO';
  const acoes: TituloFinanceiroAcao[] = [];

  if (!cancelado && flags.pode_baixar) {
    acoes.push({
      id: 'baixar',
      label: parcial
        ? FINANCEIRO_ACTION_LABELS.baixarSaldoRestante
        : modo === 'RECEBER'
          ? FINANCEIRO_ACTION_LABELS.baixarRecebimento
          : FINANCEIRO_ACTION_LABELS.baixarPagamento,
      variant: 'primary',
    });
  }
  if (flags.pode_aplicar_credito && !cancelado) {
    acoes.push({
      id: 'aplicar_credito',
      label:
        modo === 'RECEBER'
          ? FINANCEIRO_ACTION_LABELS.aplicarCredito
          : FINANCEIRO_ACTION_LABELS.aplicarCreditoFornecedor,
      variant: 'primary',
    });
  }
  if (!cancelado && flags.pode_editar) {
    acoes.push({ id: 'editar', label: FINANCEIRO_ACTION_LABELS.editar, variant: 'outline' });
  }
  if (flags.pode_abater) {
    acoes.push({
      id: 'abater_devolucao',
      label: FINANCEIRO_ACTION_LABELS.abaterDevolucao,
      variant: 'outline',
    });
  }
  if (flags.pode_estornar_baixa) {
    acoes.push({
      id: 'estornar_baixa',
      label: FINANCEIRO_ACTION_LABELS.estornarBaixa,
      variant: 'outline',
    });
  }
  if (!cancelado && flags.pode_excluir) {
    acoes.push({
      id: 'excluir',
      label: FINANCEIRO_ACTION_LABELS.excluirTitulo,
      variant: 'destructive',
    });
  }
  if (!cancelado && flags.pode_cancelar) {
    acoes.push({
      id: 'cancelar',
      label: FINANCEIRO_ACTION_LABELS.cancelarTitulo,
      variant: 'destructive',
    });
  }

  return acoes;
}

export const TIPO_MOVIMENTO_FINANCEIRO_LABELS: Record<string, string> = {
  RECEBIMENTO: 'Recebimento',
  PAGAMENTO: 'Pagamento',
  RECEBIMENTO_PARCIAL: 'Recebimento parcial',
  PAGAMENTO_PARCIAL: 'Pagamento parcial',
  ABATIMENTO: 'Abatimento',
  ABATIMENTO_DEVOLUCAO: 'Abatimento por devolução',
  GERACAO_CREDITO: 'Crédito gerado',
  USO_CREDITO: 'Uso de crédito',
  REEMBOLSO_CLIENTE: 'Reembolso ao cliente',
  REEMBOLSO_FORNECEDOR: 'Reembolso do fornecedor',
  ESTORNO: 'Estorno',
  AJUSTE_MANUAL: 'Ajuste manual',
};

export const CREDITO_TIPO_LABELS: Record<string, string> = {
  CLIENTE: 'Cliente',
  FORNECEDOR: 'Fornecedor',
};

export const CREDITO_STATUS_LABELS: Record<string, string> = {
  DISPONIVEL: 'Disponível',
  PARCIALMENTE_UTILIZADO: 'Parcialmente utilizado',
  UTILIZADO: 'Utilizado',
  CANCELADO: 'Cancelado',
};

export const CREDITO_ORIGEM_LABELS: Record<string, string> = {
  MANUAL: 'Manual',
  DEVOLUCAO: 'Devolução',
  AJUSTE: 'Ajuste',
  PAGAMENTO_A_MAIOR: 'Pagamento a maior',
  OUTROS: 'Outros',
  NFE_DEVOLUCAO_FUTURO: 'NF-e de devolução (futuro)',
};

export const FINANCEIRO_CREDITO_MESSAGES = {
  creditoClienteSucesso: 'Crédito de cliente registrado com sucesso.',
  creditoFornecedorSucesso: 'Crédito de fornecedor registrado com sucesso.',
  creditoAplicadoSucesso: 'Crédito aplicado com sucesso.',
  creditoAplicadoParcial: 'Crédito aplicado. Ainda há saldo em aberto.',
  creditoAplicadoQuitado: 'Crédito aplicado. O título foi quitado.',
  creditoCanceladoSucesso: 'Crédito cancelado com sucesso.',
  creditoExcluidoSucesso: 'Crédito excluído com sucesso.',
  tituloExcluidoSucesso: 'Título excluído com sucesso.',
  creditoEdicaoBloqueada:
    'Este crédito já possui movimentações. Para manter o histórico, apenas observações e informações complementares podem ser editadas.',
  creditoExclusaoBloqueada:
    'Este crédito possui movimentações ativas ou vínculo de origem e não pode ser excluído. Cancele ou estorne os movimentos para manter o histórico.',
  tituloExclusaoBloqueada:
    'Este título possui movimentações ativas ou vínculo de origem e não pode ser excluído. Cancele ou estorne os movimentos para manter o histórico.',
  exclusaoCreditoDescricao:
    'Este crédito foi lançado manualmente e não possui efeito financeiro ativo. A exclusão deve ser usada apenas para corrigir erro de cadastro.',
  exclusaoCreditoAvisoEstorno:
    'Este crédito possui movimentos estornados. A exclusão removerá o lançamento manual e seu histórico operacional. Use apenas se este crédito foi criado por engano.',
  exclusaoTituloDescricao:
    'Este título foi lançado manualmente e não possui efeito financeiro ativo. A exclusão deve ser usada apenas para corrigir erro de cadastro.',
  exclusaoTituloAvisoEstorno:
    'Este título possui movimentos estornados. A exclusão removerá o lançamento manual e seu histórico operacional. Use apenas se este lançamento foi criado por engano.',
  creditoUtilizadoCancelar:
    'Este crédito já possui utilização. Estorne os usos antes de cancelar o crédito integralmente.',
  abatimentoSucesso: 'Abatimento por devolução registrado com sucesso.',
  abatimentoQuitado: 'Abatimento registrado. O título foi quitado.',
  estornoUsoCreditoSucesso: 'Uso de crédito estornado. O saldo do título e do crédito foi reaberto.',
  estornoAbatimentoSucesso: 'Abatimento estornado. O saldo do título foi reaberto.',
  selecioneCredito: 'Selecione um crédito disponível.',
  informeMotivo: 'Informe o motivo.',
  informeDataCredito: 'Informe a data do crédito.',
  informeValorMaiorZero: 'Informe um valor maior que zero.',
} as const;

export function labelCreditoStatus(status: string | null | undefined, statusLabel?: string): string {
  if (statusLabel?.trim()) return statusLabel.trim();
  const key = (status || '').trim().toUpperCase();
  return CREDITO_STATUS_LABELS[key] ?? status ?? '—';
}

export function labelCreditoTipo(tipo: string | null | undefined, tipoLabel?: string): string {
  if (tipoLabel?.trim()) return tipoLabel.trim();
  const key = (tipo || '').trim().toUpperCase();
  return CREDITO_TIPO_LABELS[key] ?? tipo ?? '—';
}

export function labelCreditoOrigem(origem: string | null | undefined, origemLabel?: string): string {
  if (origemLabel?.trim()) return origemLabel.trim();
  const key = (origem || '').trim().toUpperCase();
  return CREDITO_ORIGEM_LABELS[key] ?? origem ?? '—';
}

export function labelEstornoMovimentoFinanceiro(tipoMovimento?: string | null): string {
  const key = (tipoMovimento || '').trim().toUpperCase();
  if (key === 'USO_CREDITO') return FINANCEIRO_ACTION_LABELS.estornarUsoCredito;
  if (key === 'ABATIMENTO_DEVOLUCAO') return FINANCEIRO_ACTION_LABELS.estornarAbatimento;
  return FINANCEIRO_ACTION_LABELS.estornarBaixa;
}

export function mensagemSucessoAplicarCredito(valorAberto: string | number): string {
  const saldo = parseValorFinanceiro(valorAberto);
  if (saldo <= FINANCEIRO_CENTAVO) return FINANCEIRO_CREDITO_MESSAGES.creditoAplicadoQuitado;
  return FINANCEIRO_CREDITO_MESSAGES.creditoAplicadoParcial;
}

export function mensagemSucessoAbatimento(valorAberto: string | number): string {
  const saldo = parseValorFinanceiro(valorAberto);
  if (saldo <= FINANCEIRO_CENTAVO) return FINANCEIRO_CREDITO_MESSAGES.abatimentoQuitado;
  return FINANCEIRO_CREDITO_MESSAGES.abatimentoSucesso;
}

export type CreditoFormValues = {
  valor_original: string;
  data_credito: string;
  origem_tipo: string;
  origem_numero: string;
  motivo: string;
  observacoes: string;
};

export function validarCreditoForm(
  contraparteId: number | null,
  form: CreditoFormValues,
  tipo: 'CLIENTE' | 'FORNECEDOR',
): string | null {
  if (!contraparteId) {
    return tipo === 'CLIENTE'
      ? FINANCEIRO_CLIENTE_MESSAGES.selecioneCliente
      : FINANCEIRO_FORNECEDOR_MESSAGES.selecioneFornecedor;
  }
  if (!(form.data_credito || '').trim()) return FINANCEIRO_CREDITO_MESSAGES.informeDataCredito;
  if (!(form.motivo || '').trim()) return FINANCEIRO_CREDITO_MESSAGES.informeMotivo;
  const valor = parseValorFinanceiro(form.valor_original);
  if (valor <= 0) return FINANCEIRO_CREDITO_MESSAGES.informeValorMaiorZero;
  return null;
}

export function validarAplicarCreditoForm(
  creditoId: number | null,
  valor: string,
  saldoCredito: string | number,
  saldoTitulo: string | number,
): string | null {
  if (!creditoId) return FINANCEIRO_CREDITO_MESSAGES.selecioneCredito;
  const v = parseValorFinanceiro(valor);
  if (v <= 0) return FINANCEIRO_CREDITO_MESSAGES.informeValorMaiorZero;
  if (v > parseValorFinanceiro(saldoCredito) + FINANCEIRO_CENTAVO) {
    return 'O valor excede o saldo do crédito.';
  }
  if (v > parseValorFinanceiro(saldoTitulo) + FINANCEIRO_CENTAVO) {
    return 'O valor excede o saldo em aberto do título.';
  }
  return null;
}

export function validarAbatimentoForm(valor: string, motivo: string, saldoTitulo: string | number): string | null {
  const v = parseValorFinanceiro(valor);
  if (v <= 0) return FINANCEIRO_CREDITO_MESSAGES.informeValorMaiorZero;
  if (!(motivo || '').trim()) return FINANCEIRO_CREDITO_MESSAGES.informeMotivo;
  if (v > parseValorFinanceiro(saldoTitulo) + FINANCEIRO_CENTAVO) {
    return 'O valor excede o saldo em aberto do título.';
  }
  return null;
}

export function creditosTemFiltroAtivo(filtros: {
  search?: string;
  tipo?: string;
  status?: string;
}): boolean {
  return Boolean((filtros.search || '').trim() || filtros.tipo || filtros.status);
}

export type CreditoFinanceiroOperacional = {
  id?: number;
  tipo?: string;
  status: string;
  cancelado?: boolean;
  saldo?: string | number;
  valor_utilizado?: string | number;
  contraparte_nome?: string;
  pode_aplicar?: boolean;
  pode_cancelar?: boolean;
  pode_editar?: boolean;
  pode_editar_completo?: boolean;
  pode_excluir?: boolean;
  possui_movimento?: boolean;
  possui_movimento_ativo?: boolean;
  possui_apenas_movimentos_estornados?: boolean;
  possui_aplicacao?: boolean;
  possui_aplicacao_ativa?: boolean;
  motivo_bloqueio_exclusao?: string;
  movimentos?: { id: number; estornada?: boolean; pode_estornar?: boolean; tipo_movimento?: string }[];
  eventos?: unknown[];
};

export type CreditoFinanceiroAcaoId =
  | 'aplicar'
  | 'editar'
  | 'excluir'
  | 'cancelar'
  | 'estornar_uso'
  | 'ver_historico';

export type CreditoFinanceiroAcao = {
  id: CreditoFinanceiroAcaoId;
  label: string;
  variant?: 'primary' | 'outline' | 'destructive';
};

export function getCreditoFinanceiroAcoes(credito: CreditoFinanceiroOperacional): CreditoFinanceiroAcao[] {
  const cancelado = Boolean(credito.cancelado || credito.status === 'CANCELADO');
  const status = (credito.status || '').trim().toUpperCase();
  const parcial = status === 'PARCIALMENTE_UTILIZADO';
  const utilizado = status === 'UTILIZADO';
  const acoes: CreditoFinanceiroAcao[] = [];

  if (!cancelado && credito.pode_aplicar) {
    acoes.push({
      id: 'aplicar',
      label: parcial ? 'Aplicar saldo restante' : FINANCEIRO_ACTION_LABELS.aplicarCredito,
      variant: 'primary',
    });
  }
  if (!cancelado && credito.pode_editar) {
    acoes.push({
      id: 'editar',
      label: credito.pode_editar_completo
        ? FINANCEIRO_ACTION_LABELS.editarCredito
        : 'Editar observações',
      variant: 'outline',
    });
  }
  if (!cancelado && credito.pode_excluir) {
    acoes.push({
      id: 'excluir',
      label: FINANCEIRO_ACTION_LABELS.excluirCredito,
      variant: 'destructive',
    });
  }
  if (!cancelado && credito.pode_cancelar) {
    acoes.push({
      id: 'cancelar',
      label: FINANCEIRO_ACTION_LABELS.cancelarCredito,
      variant: 'destructive',
    });
  }
  const baixaEstornavel = credito.movimentos?.find(
    (m) => !m.estornada && m.pode_estornar !== false && m.tipo_movimento === 'USO_CREDITO',
  );
  if (baixaEstornavel && (parcial || utilizado || credito.possui_aplicacao || credito.possui_aplicacao_ativa)) {
    acoes.push({
      id: 'estornar_uso',
      label: FINANCEIRO_ACTION_LABELS.estornarUsoCredito,
      variant: 'outline',
    });
  }

  return acoes;
}

export function tituloOperacionalDrawerTitulo(
  titulo: { numero?: string; cliente_nome?: string; fornecedor_nome?: string },
  modo: TituloModo,
): string {
  const contraparte = modo === 'RECEBER' ? titulo.cliente_nome : titulo.fornecedor_nome;
  const base = modo === 'RECEBER' ? 'Conta a receber' : 'Conta a pagar';
  if (contraparte?.trim()) return `${base} — ${contraparte.trim()}`;
  if (titulo.numero?.trim()) return `${base} — ${titulo.numero.trim()}`;
  return base;
}

export function creditoOperacionalDrawerTitulo(credito: {
  tipo?: string;
  contraparte_nome?: string;
}): string {
  const base = credito.tipo === 'FORNECEDOR' ? 'Crédito de fornecedor' : 'Crédito de cliente';
  if (credito.contraparte_nome?.trim()) return `${base} — ${credito.contraparte_nome.trim()}`;
  return base;
}

const ACAO_IDS_PRINCIPAIS = new Set(['baixar', 'aplicar', 'aplicar_credito']);
const ACAO_IDS_PERIGOSAS = new Set(['excluir', 'cancelar']);

export function agruparFinanceiroDrawerAcoes<T extends { id: string; label: string; variant?: string }>(
  acoes: T[],
  executar: (id: string) => void,
) {
  const map = (lista: T[]) =>
    lista.map((a) => ({
      id: a.id,
      label: a.label,
      variant: a.variant as 'primary' | 'outline' | 'destructive' | undefined,
      onClick: () => executar(a.id),
    }));

  const principal = map(acoes.filter((a) => ACAO_IDS_PRINCIPAIS.has(a.id)));
  const perigosas = map(acoes.filter((a) => ACAO_IDS_PERIGOSAS.has(a.id)));
  const secundarias = map(
    acoes.filter((a) => !ACAO_IDS_PRINCIPAIS.has(a.id) && !ACAO_IDS_PERIGOSAS.has(a.id)),
  );

  return { principal, secundarias, perigosas };
}

export function labelExclusaoIndisponivel(motivo?: string | null): string {
  return (motivo || '').trim();
}

export type FinanceiroHistoricoEvento = {
  acao?: string;
  descricao: string;
  valor?: string | null;
  titulo_numero?: string;
  criado_em: string;
  usuario_nome?: string;
};

export function humanizarDescricaoFinanceira(descricao: string, valor?: string | null): string {
  let text = (descricao || '').trim();
  if (!text) return '—';
  if (valor) {
    const fmt = formatMoneyBRL(valor);
    text = text.replace(/R\$\s*[\d.,]+/g, fmt);
  }
  return text.replace(/\s+/g, ' ').trim();
}

export function linhasDetalheHistoricoFinanceiro(evento: FinanceiroHistoricoEvento): string[] {
  const linhas: string[] = [];
  const valorFmt = evento.valor ? formatMoneyBRL(evento.valor) : null;
  if (valorFmt) linhas.push(`Valor: ${valorFmt}`);
  const motivoMatch = evento.descricao.match(/Motivo:\s*(.+)$/i);
  if (motivoMatch?.[1]) {
    linhas.push(`Motivo: ${motivoMatch[1].trim()}`);
  }
  if (evento.titulo_numero?.trim() && !evento.descricao.includes(evento.titulo_numero.trim())) {
    linhas.push(`Título: ${evento.titulo_numero.trim()}`);
  }
  return linhas;
}
