export type OpcaoFornecedor = {
  id: number;
  label: string;
  cnpj: string;
  cidade: string;
  uf: string;
};

export type OpcaoPedidoCompra = {
  id: number;
  numero: string;
  fornecedor: string;
  fornecedor_id: number | null;
  data: string;
  status: string;
  valor_total: string;
  label: string;
};

export type OpcaoPedidoCompraItem = {
  id: number;
  pedido_compra_id: number;
  produto_id: number;
  produto_nome: string;
  quantidade: string;
  quantidade_disponivel_para_vinculo: string;
  unidade: string;
  label: string;
};

export type OpcaoNfeEntradaImportada = {
  id: number;
  numero: string;
  serie: string;
  chave: string;
  chave_resumida: string;
  fornecedor: string;
  fornecedor_id: number | null;
  emissao: string;
  valor_total: string;
  status_conferencia: string | null;
  classificacao_dfe?: Record<string, unknown>;
  label: string;
};

export type OpcaoNfeEntradaImportadaItem = {
  id: number;
  nfe_entrada_historica_id: number;
  produto_id: number | null;
  produto_nome: string;
  codigo: string;
  ncm: string;
  cfop: string;
  quantidade: string;
  valor_total: string;
  label: string;
};

export type OpcaoCteConferido = {
  id: number;
  numero: string;
  serie: string;
  transportadora: string;
  transportadora_id: number | null;
  tomador: string;
  valor_total: string;
  emissao: string;
  status_conferencia: string;
  label: string;
};

export type AlocacaoVinculosExibicao = {
  fornecedor_label: string | null;
  pedido_compra_label: string | null;
  pedido_compra_id: number | null;
  nfe_entrada_label: string | null;
  nfe_entrada_historica_id?: number | null;
  nfe_entrada_status_conferencia: string | null;
  cte_label: string | null;
  cte_status_conferencia: string | null;
  tem_compra_vinculada: boolean;
  tem_nfe_entrada_vinculada: boolean;
  tem_cte_vinculado: boolean;
  alertas_vinculo: string[];
};
