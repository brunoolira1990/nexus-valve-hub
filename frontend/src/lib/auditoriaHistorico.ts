import type { AuditoriaCampoAlteracao, RegistroAuditoria } from '@/services/api/auditoria';

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

export function formatarValorAuditoria(valor: unknown): string {
  if (valor === null || valor === undefined || valor === '') return '—';
  if (typeof valor === 'boolean') return valor ? 'Sim' : 'Não';
  return String(valor);
}

export function campoEhProtegido(alt: AuditoriaCampoAlteracao): boolean {
  return Boolean(alt && 'sensivel' in alt && alt.sensivel && alt.alterado);
}

export function entradasAlteracao(registro: RegistroAuditoria): { campo: string; alt: AuditoriaCampoAlteracao }[] {
  return Object.entries(registro.alteracoes || {}).map(([campo, alt]) => ({ campo, alt }));
}
