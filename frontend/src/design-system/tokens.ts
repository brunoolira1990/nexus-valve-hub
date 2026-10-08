/** Tokens semânticos do Design System Nexus (ERP 4.0.9). */

export type StatusTone =
  | 'neutral'
  | 'info'
  | 'primary'
  | 'success'
  | 'warning'
  | 'danger'
  | 'preparation';

export type StatusBadgeVariant = 'solid' | 'soft';

export interface StatusToken {
  label: string;
  tone: StatusTone;
  /** Homologação vs produção — diferenciação visual explícita quando aplicável. */
  homologacao?: boolean;
}

/** Chaves normalizadas (lowercase, sem acentos extras). */
function norm(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}

const STATUS_MAP: Record<string, StatusToken> = {
  // Geral
  ativo: { label: 'Ativo', tone: 'success' },
  inativo: { label: 'Inativo', tone: 'neutral' },
  pendente: { label: 'Pendente', tone: 'warning' },
  concluido: { label: 'Concluído', tone: 'success' },
  cancelado: { label: 'Cancelado', tone: 'neutral' },
  // Comercial
  aberto: { label: 'Aberto', tone: 'info' },
  aberta: { label: 'Aberta', tone: 'info' },
  aprovado: { label: 'Aprovado', tone: 'success' },
  aprovada: { label: 'Aprovada', tone: 'success' },
  faturado: { label: 'Faturado', tone: 'success' },
  recusada: { label: 'Recusada', tone: 'danger' },
  rejeitada: { label: 'Rejeitada', tone: 'danger' },
  convertida: { label: 'Convertida', tone: 'success' },
  recebido: { label: 'Recebido', tone: 'success' },
  recebido_parcial: { label: 'Recebido parcial', tone: 'warning' },
  recebido_parcialmente: { label: 'Recebido parcial', tone: 'warning' },
  importada_entrada: { label: 'Importada', tone: 'success' },
  preparada_entrada: { label: 'Conferência finalizada', tone: 'primary' },
  em_faturamento: { label: 'Em faturamento', tone: 'warning' },
  parcial: { label: 'Parcialmente faturado', tone: 'warning' },
  parcialmente_faturado: { label: 'Parcialmente faturado', tone: 'warning' },
  pendente_faturamento: { label: 'Pendente de faturamento', tone: 'warning' },
  cancel: { label: 'Cancelado', tone: 'neutral' },
  // Qualidade
  emitido: { label: 'Emitido', tone: 'success' },
  revisado: { label: 'Revisado', tone: 'success' },
  validado: { label: 'Validado', tone: 'success' },
  registrado: { label: 'Registrado', tone: 'success' },
  divergente_qualidade: { label: 'Divergente', tone: 'danger' },
  reprovado: { label: 'Reprovado', tone: 'danger' },
  reprovada: { label: 'Reprovada', tone: 'danger' },
  em_analise: { label: 'Em análise', tone: 'info' },
  encerrado: { label: 'Encerrado', tone: 'neutral' },
  encerrada: { label: 'Encerrada', tone: 'neutral' },
  // Estoque
  normal: { label: 'Normal', tone: 'neutral' },
  baixo_estoque: { label: 'Baixo estoque', tone: 'warning' },
  saldo_negativo: { label: 'Saldo negativo', tone: 'danger' },
  sem_ncm: { label: 'Sem NCM', tone: 'warning' },
  sem_movimentacao: { label: 'Sem movimentação', tone: 'neutral' },
  // Atendimento estoque
  atendido: { label: 'Atendido', tone: 'success' },
  em_separacao: { label: 'Em separação', tone: 'info' },
  separado: { label: 'Separado', tone: 'success' },
  entrada: { label: 'Entrada', tone: 'info' },
  saida: { label: 'Saída', tone: 'success' },
  // CT-e / XML
  importado: { label: 'Importado', tone: 'success' },
  processado_xml: { label: 'Processado', tone: 'success' },
  erro_processamento: { label: 'Erro processamento', tone: 'danger' },
  reprocessar: { label: 'Reprocessar', tone: 'warning' },
  // Fiscal config
  incompleto: { label: 'Incompleto', tone: 'warning' },
  revisar: { label: 'Revisar', tone: 'warning' },
  // Modelo operacional 4.0.10
  entrada_conciliada: { label: 'Entrada conciliada', tone: 'success' },
  entrada_pendente: { label: 'Entrada pendente', tone: 'warning' },
  retirada_fornecedor: { label: 'Retirada fornecedor', tone: 'info' },
  retirada_fornecedor_transportadora: { label: 'Retirada fornecedor → transportadora', tone: 'info' },
  entrega_direta: { label: 'Entrega direta', tone: 'info' },
  atendimento_misto: { label: 'Atendimento misto', tone: 'warning' },
  nao_definido: { label: 'Não definido', tone: 'neutral' },
  atendimento_nao_definido: { label: 'Atendimento não definido', tone: 'neutral' },
  compra_vinculada: { label: 'Compra vinculada', tone: 'success' },
  sem_compra_vinculada: { label: 'Sem compra vinculada', tone: 'neutral' },
  cte_conferido: { label: 'CT-e conferido', tone: 'success' },
  sem_cte: { label: 'Sem CT-e', tone: 'neutral' },
  sem_bloqueio_operacional: { label: 'Sem bloqueio operacional', tone: 'info' },
  conciliada: { label: 'Conciliada', tone: 'success' },
  recebida: { label: 'Recebida', tone: 'info' },
  // NF-e / emissão
  rascunho: { label: 'Rascunho', tone: 'neutral' },
  em_conferencia: { label: 'Em conferência', tone: 'info' },
  pronta: { label: 'Pronta', tone: 'primary' },
  pronta_para_emissao: { label: 'Pronta para emissão', tone: 'primary' },
  autorizada: { label: 'Autorizada', tone: 'success' },
  autorizada_homologacao: { label: 'Autorizada homologação', tone: 'success', homologacao: true },
  autorizada_producao: { label: 'Autorizada produção', tone: 'success' },
  rejeitada_homologacao: { label: 'Rejeitada homologação', tone: 'danger', homologacao: true },
  erro_transmissao: { label: 'Erro transmissão', tone: 'danger' },
  cancelada: { label: 'Cancelada', tone: 'neutral' },
  cancelada_interna: { label: 'Cancelada interna', tone: 'neutral' },
  // DF-e 4.0.10.1
  homologacao: { label: 'Homologação', tone: 'warning', homologacao: true },
  sem_valor_fiscal: { label: 'Sem valor fiscal', tone: 'neutral', homologacao: true },
  fora_apuracao: { label: 'Fora da apuração', tone: 'neutral' },
  base_importada: { label: 'Base importada', tone: 'info' },
  producao: { label: 'Produção', tone: 'success' },
  apura: { label: 'Apura', tone: 'success' },
  sem_efeito_operacional_automatico: { label: 'Sem efeito operacional automático', tone: 'neutral' },
  alimenta_precificacao: { label: 'Alimenta precificação', tone: 'info' },
  conferida: { label: 'Conferida', tone: 'success' },
  conferido: { label: 'Conferido', tone: 'success' },
  preparada: { label: 'Conferência finalizada', tone: 'info' },
  divergente: { label: 'Divergente', tone: 'warning' },
  importada: { label: 'Importada', tone: 'neutral' },
  ignorado: { label: 'Ignorado', tone: 'neutral' },
  processado: { label: 'Processado', tone: 'info' },
  sem_financeiro_automatico: { label: 'Sem financeiro automático', tone: 'neutral' },
  sem_expedicao_automatica: { label: 'Sem expedição automática', tone: 'neutral' },
  xml_importado: { label: 'XML importado', tone: 'info' },
  operacional: { label: 'Operacional', tone: 'primary' },
  // Financeiro futuro
  em_preparacao: { label: 'Em preparação', tone: 'preparation' },
  vencido: { label: 'Vencido', tone: 'danger' },
  pago: { label: 'Pago', tone: 'success' },
  // Financeiro operacional 4.0.14
  em_aberto: { label: 'Em aberto', tone: 'info' },
  parcialmente_recebido: { label: 'Parcialmente recebido', tone: 'warning' },
  parcialmente_pago: { label: 'Parcialmente pago', tone: 'warning' },
  estornado: { label: 'Estornado', tone: 'neutral' },
};

export function resolveStatusToken(status: string): StatusToken {
  const key = norm(status);
  return STATUS_MAP[key] ?? { label: status, tone: 'neutral' };
}

export const statusToneClasses: Record<StatusTone, { soft: string; solid: string }> = {
  neutral: {
    soft: 'bg-muted text-muted-foreground ring-1 ring-border',
    solid: 'bg-neutral/20 text-foreground',
  },
  info: {
    soft: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
    solid: 'bg-info text-info-foreground',
  },
  primary: {
    soft: 'bg-primary/10 text-primary ring-1 ring-primary/20',
    solid: 'bg-primary text-primary-foreground',
  },
  success: {
    soft: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
    solid: 'bg-success text-success-foreground',
  },
  warning: {
    soft: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200',
    solid: 'bg-warning text-warning-foreground',
  },
  danger: {
    soft: 'bg-red-50 text-red-700 ring-1 ring-red-200',
    solid: 'bg-destructive text-destructive-foreground',
  },
  preparation: {
    soft: 'bg-violet-50 text-violet-700 ring-1 ring-violet-200',
    solid: 'bg-violet-600 text-white',
  },
};
