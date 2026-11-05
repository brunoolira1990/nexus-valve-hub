import type {
  AuditoriaCampoAlteracao,
  AuditoriaValorResolvido,
  RegistroAuditoria,
} from '@/services/api/auditoria';

export const AUDITORIA_ESCOPO_TEXTO =
  'Histórico dos campos principais do cadastro. Contatos, endereços e alterações em lote ainda não fazem parte desta versão.';

export const AUDITORIA_VALOR_PROTEGIDO = 'Valor protegido alterado';

const LABELS_CAMPOS: Record<string, string> = {
  razao_social: 'Razão social',
  nome_fantasia: 'Nome fantasia',
  ie: 'IE',
  ie_isento: 'IE isento',
  inscricao_municipal: 'Inscrição municipal',
  suframa: 'SUFRAMA',
  limite_credito: 'Limite de crédito',
  condicao_pagamento_texto: 'Condição de pagamento',
  quantidade_parcelas: 'Quantidade de parcelas',
  bloqueado: 'Bloqueado',
  ativo: 'Ativo',
  vendedor_padrao: 'Vendedor padrão',
  regime_tributario: 'Regime tributário',
  cnae: 'CNAE',
  transportadora_padrao_id: 'Transportadora padrão',
  ddd: 'DDD',
  tipo_conta: 'Tipo de conta',
  cnpj: 'CNPJ',
  email: 'E-mail',
  email_nf: 'E-mail NF',
  telefone: 'Telefone',
  telefone_alternativo: 'Telefone alternativo',
  celular: 'Celular',
  contato_responsavel: 'Contato responsável',
  logradouro: 'Logradouro',
  numero: 'Número',
  complemento: 'Complemento',
  bairro: 'Bairro',
  cidade: 'Cidade',
  uf: 'UF',
  cep: 'CEP',
  observacoes: 'Observações',
  informacoes_complementares_nfe: 'Informações complementares NF-e',
  integracao_texto: 'Integração',
  banco: 'Banco',
  agencia: 'Agência',
  conta: 'Conta',
  codigo_completo: 'Código',
  descricao: 'Descrição',
  unidade: 'Unidade',
  unidade_especifica: 'Unidade específica',
  ncm: 'NCM',
  ncm_especifico: 'NCM específico',
  modo_codigo: 'Modo de código',
  figura: 'Figura',
  sufixo: 'Sufixo',
  schedule: 'Schedule',
  polegada_principal: 'Polegada principal',
  polegada_secundaria: 'Polegada secundária',
  material: 'Material',
  tipo_peca: 'Tipo de peça',
  pressao_nominal: 'Pressão nominal',
  norma: 'Norma',
  conexao: 'Conexão',
  familia_id: 'Família',
  tipo_fisico: 'Tipo físico',
  tipo_controle_unidade: 'Controle de unidade',
  unidade_estoque: 'Unidade estoque',
  unidade_venda_padrao: 'Unidade venda',
  unidade_compra_padrao: 'Unidade compra',
  unidade_fiscal: 'Unidade fiscal',
  dimensao_codigo: 'Dimensão (código)',
  dimensao_descricao: 'Dimensão (descrição)',
  preco_custo: 'Preço de custo',
  preco_venda: 'Preço de venda',
};

export function labelCampoAuditoria(campo: string): string {
  return LABELS_CAMPOS[campo] || campo.replace(/_/g, ' ');
}

export function labelOperacaoAuditoria(operacao: string): string {
  if (operacao === 'CREATE') return 'Criação';
  if (operacao === 'UPDATE') return 'Atualização';
  return operacao;
}

/**
 * Fase 1 da entrada de terceiros (PR 2): labels humanos das ações de domínio
 * gravadas na coluna `acao` por apps/fiscal/auditoria_entrada.py. As chaves
 * batem com ACOES_CONFERENCIA/ESTOQUE/FINANCEIRO/DEVOLUCAO daquele módulo —
 * o disco é a fonte; `gerar_contas_pagar_cte` NÃO existe lá (o CT-e reusa
 * 'gerar_contas_pagar'), por isso não há entrada no map.
 * PR 3: `salvar_rateio` entrou no map junto do plug da action frete/salvar-rateio
 * (última ação de domínio ligada; adicionada a ACOES_FINANCEIRO no mesmo PR).
 */
export const ACAO_LABELS: Record<string, string> = {
  conferir: 'Conferiu a nota',
  reabrir: 'Reabriu a conferência',
  marcar_divergente: 'Marcou como divergente',
  desvincular_alocacoes_venda: 'Desvinculou alocações de venda',
  preparar_estoque: 'Preparou o estoque',
  aplicar_estoque: 'Aplicou o estoque',
  reverter_estoque: 'Reverteu o estoque',
  gerar_contas_pagar: 'Gerou contas a pagar',
  estornar_contas: 'Estornou as contas a pagar',
  gerar_saida_devolucao_compra: 'Gerou devolução de compra',
  salvar_rateio: 'Salvou o rateio do frete',
};

export function labelAcaoAuditoria(acao: string): string {
  return ACAO_LABELS[acao] ?? acao.replace(/_/g, ' ');
}

export function formatarValorAuditoria(valor: unknown): string {
  if (valor === null || valor === undefined || valor === '') return '—';
  if (typeof valor === 'boolean') return valor ? 'Sim' : 'Não';
  if (typeof valor === 'object') {
    const nome = (valor as AuditoriaValorResolvido).nome;
    return nome ? String(nome) : '—';
  }
  return String(valor);
}

export function campoEhProtegido(alt: AuditoriaCampoAlteracao): boolean {
  return Boolean(alt && 'sensivel' in alt && alt.sensivel && alt.alterado);
}

/**
 * Entradas de diff de campo do registro. Chaves iniciadas por '_' são chaves
 * reservadas do backend (`_snapshot`, `_detalhes` do ramo de evento puro da
 * Fase 1) e NUNCA são diffs de campo — ficam fora daqui por construção: todo
 * consumidor do diff (o painel de histórico) herda o filtro.
 */
export function entradasAlteracao(registro: RegistroAuditoria): { campo: string; alt: AuditoriaCampoAlteracao }[] {
  return Object.entries(registro.alteracoes || {})
    .filter(([campo]) => !campo.startsWith('_'))
    .map(([campo, alt]) => ({ campo, alt }));
}
