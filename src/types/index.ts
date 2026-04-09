export interface Empresa {
  id: number;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  im: string;
  regime_tributario: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email: string;
  site: string;
  empresa_pai_id: number | null;
  certificado_digital: string;
  senha_certificado: string;
}

export interface Cliente {
  id: number;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email: string;
  contato_responsavel: string;
  observacoes: string;
}

export interface Fornecedor {
  id: number;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email: string;
  contato_responsavel: string;
  observacoes: string;
}

export interface Transportadora {
  id: number;
  razao_social: string;
  cnpj: string;
  ie: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  email: string;
  placa_padrao: string;
  uf_placa: string;
}

export interface Produto {
  id: number;
  figura: string;
  sufixo: string;
  schedule: string;
  polegada_principal: string;
  polegada_secundaria: string;
  descricao: string;
  material: string;
  tipo_peca: string;
  pressao_nominal: string;
  norma: string;
  conexao: string;
  ncm: string;
  preco_custo: number;
  preco_venda: number;
  estoque_minimo: number;
  codigo_completo: string;
}

export interface ComposicaoQuimica {
  C: number; Mn: number; P: number; S: number; Si: number; Ni: number;
  Cr: number; Mo: number; Cu: number; V: number; Nb: number; Al: number;
  Ti: number; N: number; Zn: number; Fe: number; Sn: number; Pb: number;
  Ca: number; Ta: number; W: number; Li: number; CO: number;
}

export interface Tracao {
  norma: string; corpo_prova: string; direcao: string; posicao: string;
  temperatura: number; limite_escoamento: number; limite_resistencia: number;
  alongamento: number; estriccao: number; dureza: string; tratamento_termico: string;
}

export interface Impacto {
  norma: string; corpo_prova: string; direcao: string; posicao: string;
  temperatura: number; valor_a: number; valor_b: number; valor_c: number; media: number;
}

export interface Corrida {
  id: number;
  numero: string;
  produto_id: number;
  produto_nome: string;
  fornecedor_id: number;
  fornecedor_nome: string;
  data_recebimento: string;
  nf_entrada: string;
  composicao_quimica: ComposicaoQuimica;
  tracao: Tracao;
  impacto: Impacto;
}

export interface RegraFiscal {
  id: number;
  ncm: string;
  uf_origem: string;
  uf_destino: string;
  operacao: 'Entrada' | 'Saída';
  cfop: string;
  cst_icms: string;
  aliquota_icms: number;
  cst_pis: string;
  aliquota_pis: number;
  cst_cofins: string;
  aliquota_cofins: number;
  cst_ipi: string;
  aliquota_ipi: number;
  base_calculo: string;
}

export interface ItemProposta {
  id: number;
  produto_id: number;
  produto_nome: string;
  quantidade: number;
  valor_unitario: number;
  desconto: number;
}

export interface Proposta {
  id: number;
  numero: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  validade: string;
  vendedor: string;
  status: string;
  valor_total: number;
  itens: ItemProposta[];
}

export interface ItemPedido {
  id: number;
  produto_id: number;
  produto_nome: string;
  quantidade: number;
  valor_unitario: number;
  corrida_id?: number;
  corrida_numero?: string;
}

export interface PedidoVenda {
  id: number;
  numero: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  status: string;
  valor_total: number;
  proposta_id?: number;
  itens: ItemPedido[];
}

export interface PedidoCompra {
  id: number;
  numero: string;
  fornecedor_id: number;
  fornecedor_nome: string;
  data: string;
  status: string;
  valor_total: number;
  itens: ItemPedido[];
}

export interface ItemNFe {
  id: number;
  produto_id: number;
  produto_nome: string;
  quantidade: number;
  valor: number;
  corrida_id?: number;
  corrida_numero?: string;
}

export interface NFeEntrada {
  id: number;
  numero: string;
  fornecedor_id: number;
  fornecedor_nome: string;
  data: string;
  valor_total: number;
  pedido_compra_id?: number;
  cte_id?: number;
  itens: ItemNFe[];
}

export interface NFeSaida {
  id: number;
  numero: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  valor_total: number;
  status: string;
  pedido_venda_id?: number;
  itens: ItemNFe[];
}

export interface CTeEntrada {
  id: number;
  numero: string;
  transportadora_id: number;
  transportadora_nome: string;
  tomador_id: number;
  tomador_nome: string;
  valor_frete: number;
  data: string;
  nfe_ids: number[];
}

export interface EstoqueItem {
  produto_id: number;
  produto_nome: string;
  corrida_id: number;
  corrida_numero: string;
  saldo: number;
}

export interface ApuracaoFiscal {
  periodo: string;
  receita_bruta: number;
  irpj: number;
  csll: number;
  pis: number;
  cofins: number;
  icms: number;
  ipi: number;
  cbs: number;
  ibs: number;
}

export interface ContaContabil {
  id: number;
  codigo: string;
  nome: string;
  tipo: string;
  pai_id: number | null;
  filhos?: ContaContabil[];
}

export interface Balancete {
  conta_id: number;
  conta_codigo: string;
  conta_nome: string;
  debito: number;
  credito: number;
  saldo: number;
}

export const UFS = [
  'AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA',
  'PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'
];

export const POLEGADAS = ['1/2"','3/4"','1"','1 1/4"','1 1/2"','2"','2 1/2"','3"','4"','6"','8"','10"','12"'];

export const MATERIAIS = ['Aço Carbono','Aço Inoxidável','Aço Liga','Ferro Fundido','Bronze','Latão'];
