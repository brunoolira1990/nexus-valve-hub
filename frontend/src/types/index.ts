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
  certificado_arquivo?: File | string | null;
  certificado_validade?: string | null;
  logotipo?: File | string | null;
  criado_em?: string | null;
  atualizado_em?: string | null;
  /** Só envio; não vem da API (write_only no backend). */
  senha_certificado?: string;
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
  inscricao_municipal: string;
  suframa: string;
  email_nf: string;
  telefone_alternativo: string;
  celular: string;
  limite_credito: number;
  condicao_pagamento_texto: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  transportadora_padrao_id: number | null;
  vendedor_padrao: string;
  bloqueado: boolean;
  ativo: boolean;
  ddd: string;
  banco: string;
  agencia: string;
  conta: string;
  tipo_conta: string;
  cnae: string;
  regime_tributario: string;
  integracao_texto: string;
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
  inscricao_municipal: string;
  suframa: string;
  email_nf: string;
  telefone_alternativo: string;
  celular: string;
  condicao_pagamento_texto: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  transportadora_padrao_id: number | null;
  prazo_entrega: number;
  ativo: boolean;
  ddd: string;
  banco: string;
  agencia: string;
  conta: string;
  tipo_conta: string;
  cnae: string;
  regime_tributario: string;
  integracao_texto: string;
}

export interface Transportadora {
  id: number;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  inscricao_municipal: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  cep: string;
  telefone: string;
  celular: string;
  email: string;
  contato: string;
  placa_padrao: string;
  uf_placa: string;
  valor_km: number;
  ativo: boolean;
  observacoes: string;
  ddd: string;
  suframa: string;
  email_nf: string;
  banco: string;
  agencia: string;
  conta: string;
  tipo_conta: string;
  cnae: string;
  regime_tributario: string;
  integracao_texto: string;
}

export type ModoCodigoProduto = 'LEGADO' | 'INTERNO' | 'MANUAL';
export type TipoControleUnidade =
  | 'PECA'
  | 'DIMENSIONAL'
  | 'PESO'
  | 'LINEAR'
  | 'LINEAR_PESO'
  | 'CHAPA'
  | 'TUBO'
  | 'BARRA'
  | 'PERFIL';
export type TipoFisicoProduto =
  | 'PECA'
  | 'TUBO'
  | 'BARRA_REDONDA'
  | 'BARRA_CHATA'
  | 'BARRA_SEXTAVADA'
  | 'CHAPA'
  | 'DISCO'
  | 'PERFIL'
  | 'CANTONEIRA'
  | 'OUTRO';

export type TipoRegraCodigo =
  | 'BASE_POLEGADA'
  | 'BASE_ROSCA_POLEGADA'
  | 'BASE_DUAS_POLEGADAS'
  | 'BASE_ROSCA_DUAS_POLEGADAS'
  | 'BASE_SCHEDULE_POLEGADA'
  | 'BASE_SCHEDULE_DUAS_POLEGADAS'
  | 'BASE_ROSCA_SCHEDULE_POLEGADA'
  | 'BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS'
  | 'UNDERSCORE_POLEGADA'
  | 'MANUAL_FABRICANTE';

export interface FamiliaProduto {
  id: number;
  codigo_figura: string;
  descricao_base: string;
  tipo_regra_codigo: TipoRegraCodigo;
  usa_rosca_conexao: boolean;
  usa_schedule: boolean;
  usa_polegada_principal: boolean;
  usa_polegada_secundaria: boolean;
  separador_base_medidas: string;
  ncm_padrao?: number | null;
  ncm_padrao_id?: number | null;
  ncm_padrao_info?: { id: number; codigo: string; descricao: string } | null;
  unidade_padrao?: string;
  material_base?: string;
  pressao_base?: string;
  norma_base?: string;
  conexao_base?: string;
  tipo_fisico?: TipoFisicoProduto;
  tipo_controle_unidade?: TipoControleUnidade;
  unidade_estoque_padrao?: string;
  unidade_venda_padrao?: string;
  unidade_compra_padrao?: string;
  unidade_fiscal_padrao?: string;
  unidades_venda_permitidas?: string[];
  unidades_compra_permitidas?: string[];
  comprimento_padrao_barra_m?: number | null;
  peso_por_metro_kg?: number | null;
  peso_por_peca_kg?: number | null;
  peso_por_chapa_kg?: number | null;
  densidade?: number | null;
  usa_conversao_dimensional?: boolean;
  observacoes_conversao?: string;
  polegadas_permitidas?: Array<{ id: number; codigo: string; descricao: string; tipo: 'principal' | 'secundaria' | 'ambas' }>;
  roscas_permitidas?: Array<{ id: number; codigo: string; descricao: string; padrao_da_familia: boolean }>;
  schedules_permitidos?: Array<{ id: number; codigo_schedule: string; descricao: string; padrao_da_familia: boolean }>;
  rosca_padrao_id?: number | null;
  schedule_padrao_id?: number | null;
  ativo: boolean;
}

export interface RoscaConexao {
  id: number;
  codigo: string;
  descricao: string;
  observacao?: string;
  ativo: boolean;
}

export interface ScheduleEspessura {
  id: number;
  codigo_schedule: string;
  descricao: string;
  ativo: boolean;
}

export interface Polegada {
  id: number;
  codigo?: string;
  codigo_oficial?: string;
  descricao: string;
  valor_decimal?: string;
  valor_mm?: string;
  aliases?: string | string[];
  ativo?: boolean;
  origem?: string;
  observacoes?: string;
  label?: string;
}

export type PolegadaItem = Polegada;

export interface Produto {
  id: number;
  modo_codigo?: ModoCodigoProduto;
  familia_id?: number | null;
  rosca_conexao_id?: number | null;
  schedule_ref_id?: number | null;
  polegada_principal_ref_id?: number | null;
  polegada_secundaria_ref_id?: number | null;
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
  unidade?: string;
  ncm_especifico?: string;
  unidade_especifica?: string;
  ncm_efetivo?: { id: number | null; codigo: string; descricao: string } | null;
  ncm_origem?: 'produto' | 'familia' | 'nao_definido';
  unidade_efetiva?: string;
  tipo_controle_unidade?: TipoControleUnidade | '';
  tipo_fisico?: TipoFisicoProduto | '';
  unidade_estoque?: string;
  unidade_venda_padrao?: string;
  unidade_compra_padrao?: string;
  unidade_fiscal?: string;
  unidades_venda_permitidas?: string[];
  unidades_compra_permitidas?: string[];
  observacoes_conversao?: string;
  comprimento_padrao_barra_m?: number | null;
  peso_por_metro_kg?: number | null;
  peso_por_peca_kg?: number | null;
  peso_por_chapa_kg?: number | null;
  densidade?: number | null;
  usa_conversao_dimensional?: boolean;
  tipo_controle_unidade_efetivo?: TipoControleUnidade;
  tipo_fisico_efetivo?: TipoFisicoProduto;
  unidade_estoque_efetiva?: string;
  unidade_venda_efetiva?: string;
  unidade_compra_efetiva?: string;
  unidade_fiscal_efetiva?: string;
  unidades_venda_permitidas_efetivas?: string[];
  usa_conversao_dimensional_efetivo?: boolean;
  origem_ncm?: 'familia' | 'produto';
  origem_unidade?: 'familia' | 'produto';
  alertas?: string[];
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

export type CertificadoQualidadeStatus = 'rascunho' | 'emitido' | 'cancelado';
export type CertificadoQualidadeTipo = 'PADRAO_POR_NFE' | 'VALVULA_COMPONENTES';

export interface ItemCertificadoQualidade {
  id?: number;
  ordem: number;
  tipo_dados_tecnicos?: 'PADRAO_ITEM' | 'VALVULA_COMPONENTES';
  produto?: number | null;
  codigo_produto: string;
  descricao_material: string;
  quantidade: number;
  unidade: string;
  norma: string;
  corrida: string;
  lote?: string;
  ncm?: string;
  status_vinculo_produto?: 'VINCULADO' | 'NAO_VINCULADO';
  produto_codigo?: string;
  produto_descricao?: string;
  produto_ncm_efetivo?: string;
  produto_snapshot?: Record<string, unknown>;
  origem_rastreabilidade_tipo?: string;
  origem_status_tecnico?: string;
  origem_observacoes?: string;
  observacoes_item?: string;
  composicao_json?: Record<string, unknown>;
  ensaio_tracao_json?: Record<string, unknown>;
  ensaio_impacto_json?: Record<string, unknown>;
  certificado_fornecedor_origem_id?: number | null;
  item_certificado_fornecedor_origem_id?: number | null;
  fornecedor_nome_snapshot?: string;
  nf_entrada_snapshot?: string;
  codigo_item_fornecedor_snapshot?: string;
  descricao_item_fornecedor_snapshot?: string;
  numero_certificado_fornecedor_item_snapshot?: string;
  corrida_snapshot?: string;
  lote_snapshot?: string;
  incluir_no_certificado?: boolean;
  motivo_nao_inclusao?: string;
  observacao_nao_inclusao?: string;
  componentes?: ItemCertificadoQualidadeComponente[];
}

export interface CorridaDisponivelCertificadoQualidade {
  corrida: string;
  valor_selecao?: string;
  lote?: string;
  saldo?: string;
  unidade?: string;
  fornecedor?: string;
  nf_entrada?: string;
  certificado_fornecedor?: string;
  certificado_fornecedor_id?: number | null;
  item_certificado_fornecedor_id?: number | null;
  status_certificado_fornecedor?: string;
  status_origem_tecnica?: string;
  tem_dados_tecnicos?: boolean;
  norma?: string;
  ncm?: string;
  origem?: string;
  alertas?: string[];
  composicao_json?: Record<string, unknown>;
  ensaio_tracao_json?: Record<string, unknown>;
  ensaio_impacto_json?: Record<string, unknown>;
  numero_certificado_fornecedor_item?: string;
  observacoes_origem?: string;
}

export interface ItemCertificadoQualidadeComponente {
  id?: number;
  ordem: number;
  nome_componente: string;
  descricao_componente?: string;
  norma?: string;
  corrida?: string;
  lote?: string;
  revisao_corrida?: string;
  numero_certificado_fornecedor_componente?: string;
  numero_certificado_fornecedor_componente_snapshot?: string;
  quantidade?: number | null;
  composicao_json?: Record<string, unknown>;
  ensaio_tracao_json?: Record<string, unknown>;
  ensaio_impacto_json?: Record<string, unknown>;
  observacoes?: string;
  ativo?: boolean;
}

export interface CertificadoQualidade {
  id: number;
  numero: string;
  serie: string;
  numero_formatado: string;
  cliente?: number | null;
  cliente_nome_snapshot: string;
  cliente_cnpj_snapshot?: string;
  pedido_cliente?: string;
  nota_fiscal_numero: string;
  nota_fiscal?: number | null;
  nota_fiscal_historica?: number | null;
  data_emissao?: string | null;
  observacoes?: string;
  texto_padrao?: string;
  status: CertificadoQualidadeStatus;
  tipo_certificado: CertificadoQualidadeTipo;
  criado_em: string;
  atualizado_em: string;
  itens: ItemCertificadoQualidade[];
}

export type CertificadoFornecedorStatus = 'rascunho' | 'registrado' | 'cancelado';
export type TipoDadosTecnicosItem = 'PADRAO_ITEM' | 'VALVULA_COMPONENTES';

export interface ItemCertificadoFornecedorEntradaComponente {
  id?: number;
  ordem: number;
  nome_componente: string;
  descricao_componente?: string;
  norma?: string;
  corrida?: string;
  lote?: string;
  revisao_corrida?: string;
  numero_certificado_fornecedor_componente?: string;
  quantidade?: number | null;
  composicao_json?: Record<string, unknown>;
  ensaio_tracao_json?: Record<string, unknown>;
  ensaio_impacto_json?: Record<string, unknown>;
  observacoes?: string;
  ativo?: boolean;
}

export interface ItemCertificadoFornecedorEntrada {
  id?: number;
  ordem: number;
  produto?: number | null;
  codigo_produto: string;
  descricao_material: string;
  quantidade: number;
  unidade: string;
  ncm?: string;
  norma: string;
  corrida: string;
  lote?: string;
  numero_certificado_fornecedor_item?: string;
  data_certificado_fornecedor_item?: string | null;
  pagina_certificado_fornecedor?: string;
  observacao_origem_certificado?: string;
  tipo_dados_tecnicos?: TipoDadosTecnicosItem;
  composicao_json?: Record<string, unknown>;
  ensaio_tracao_json?: Record<string, unknown>;
  ensaio_impacto_json?: Record<string, unknown>;
  observacoes_item?: string;
  ativo?: boolean;
  componentes?: ItemCertificadoFornecedorEntradaComponente[];
}

export interface CertificadoFornecedorEntrada {
  id: number;
  numero_certificado_fornecedor?: string;
  fornecedor?: number | null;
  fornecedor_nome_snapshot: string;
  fornecedor_cnpj_snapshot?: string;
  nf_entrada_historica?: number | null;
  nf_entrada_operacional?: number | null;
  numero_nf_entrada?: string;
  serie_nf_entrada?: string;
  data_nf_entrada?: string | null;
  empresa_destinataria?: number | null;
  status: CertificadoFornecedorStatus;
  observacoes?: string;
  arquivo_original?: File | string | null;
  criado_em: string;
  atualizado_em: string;
  quantidade_itens?: number;
  itens: ItemCertificadoFornecedorEntrada[];
}

export interface DadosTecnicosFornecedorResultado {
  id: number;
  certificado_fornecedor_id: number;
  fornecedor?: number | null;
  fornecedor_nome?: string;
  numero_nf_entrada?: string;
  data_nf_entrada?: string;
  numero_certificado_fornecedor?: string;
  numero_certificado_fornecedor_item?: string;
  status_certificado_fornecedor?: string;
  produto?: number | null;
  codigo_produto: string;
  descricao_material: string;
  norma?: string;
  corrida?: string;
  lote?: string;
  tipo_dados_tecnicos: TipoDadosTecnicosItem;
  confianca_correspondencia?: 'ALTA' | 'MEDIA_ALTA' | 'MEDIA' | 'BAIXA';
  tipo_correspondencia?: string;
  mensagem_contexto?: string;
  norma_compativel?: boolean;
  produto_relacionado?: boolean;
  score?: number;
  aviso_divergencia_codigo?: string;
  aviso_divergencia_item?: string;
  aviso_divergencia_dados_tecnicos?: string;
  aviso_certificado_rascunho?: string;
  composicao_json?: Record<string, unknown>;
  ensaio_tracao_json?: Record<string, unknown>;
  ensaio_impacto_json?: Record<string, unknown>;
  componentes?: ItemCertificadoFornecedorEntradaComponente[];
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
  produto_id?: number | null;
  produto_nome: string;
  descricao_avulsa?: string;
  /** NCM manual em item avulso (regra fiscal). */
  ncm_avulso?: string;
  quantidade: number;
  unidade_negociada?: string;
  quantidade_negociada?: number;
  unidade_estoque_calculada?: string;
  quantidade_estoque_calculada?: number;
  peso_total_kg?: number;
  metros_total?: number;
  barras_total?: number;
  valor_unitario: number;
  preco_por_unidade_negociada?: number;
  preco_por_kg?: number;
  preco_por_metro?: number;
  fator_conversao?: number;
  desconto: number;
  custo_utilizado: number;
  frete: number;
  despesas: number;
  ipi_entrada_percentual?: number;
  ipi_custo: number;
  st_custo: number;
  outros_impostos_custo: number;
  custo_final: number;
  icms_saida_percentual?: number;
  pis_saida_percentual?: number;
  cofins_saida_percentual?: number;
  ipi_saida_percentual?: number;
  regra_fiscal_id?: number | null;
  irpj_estimado_percentual?: number;
  csll_estimada_percentual?: number;
  comissao_percentual?: number;
  frete_saida?: number;
  outras_despesas_saida?: number;
  modo_preco: 'sugerido' | 'manual';
  preco_sugerido: number;
  preco_final: number;
  margem_resultante: number;
  lucro_resultante: number;
  /** Somente leitura (API / cálculo local). */
  ipi_entrada_valor?: number;
  custo_carregado?: number;
  preco_base?: number;
  percentual_saida_total?: number;
  valor_carga_saida?: number;
  estrategia_formacao?: 'margem' | 'markup';
  alvo_percentual?: number;
}

export interface Proposta {
  id: number;
  numero: string;
  cliente_id?: number | null;
  cliente_nome: string;
  cliente_avulso_nome?: string;
  empresa_emitente_id?: number | null;
  empresa_emitente_nome?: string;
  data: string;
  validade: string;
  vendedor: string;
  status: string;
  condicao_pagamento_texto: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  vencimentos_previstos: string[];
  valor_total: number;
  /** Derivada da empresa emitente (somente leitura na API). */
  uf_origem?: string;
  uf_destino_avulso?: string;
  /** Fluxo comercial: sempre saída (somente leitura na API). */
  operacao_fiscal?: string;
  itens: ItemProposta[];
}

export interface ItemPedido {
  id: number;
  produto_id: number;
  produto_nome: string;
  quantidade: number;
  unidade_negociada?: string;
  quantidade_negociada?: number;
  unidade_estoque_calculada?: string;
  quantidade_estoque_calculada?: number;
  peso_total_kg?: number;
  metros_total?: number;
  barras_total?: number;
  valor_unitario: number;
  preco_por_unidade_negociada?: number;
  preco_por_kg?: number;
  preco_por_metro?: number;
  fator_conversao?: number;
  corrida_id?: number;
  corrida_numero?: string;
}

export interface PedidoVenda {
  id: number;
  numero: string;
  empresa_emitente_id?: number | null;
  empresa_emitente_nome?: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  status: string;
  condicao_pagamento_texto: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  vencimentos_previstos: string[];
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
  condicao_pagamento_texto: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  vencimentos_previstos: string[];
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
  fornecedor_cnpj?: string;
  data: string;
  valor_total: number;
  serie?: string;
  chave_acesso?: string;
  pedido_compra_id?: number;
  cte_id?: number;
  itens: ItemNFe[];
}

export type StatusItemConferenciaNFeEntrada =
  | 'PENDENTE_PRODUTO'
  | 'PRODUTO_VINCULADO'
  | 'CONFERIDO'
  | 'DIVERGENTE'
  | 'IGNORADO';

export interface ItemConferenciaNFeEntrada {
  id: number;
  item_nfe_historico: number;
  produto_id?: number | null;
  produto_nome?: string;
  item_pedido_compra_id?: number | null;
  status: StatusItemConferenciaNFeEntrada;
  motivo_ignorado?: string;
  observacao?: string;
  corrida?: string;
  lote?: string;
  unidade_nf: string;
  quantidade_nf: number;
  valor_unitario_nf: number;
  valor_total_nf: number;
  unidade_estoque_calculada?: string;
  quantidade_estoque_calculada?: number;
  peso_total_kg?: number;
  metros_total?: number;
  barras_total?: number;
  toneladas_total?: number;
  divergencias?: string[];
  alertas?: string[];
  dados_nf?: {
    codigo_fornecedor: string;
    descricao_fornecedor: string;
    ncm: string;
    cfop: string;
    unidade_nf: string;
  };
  sugestoes_produto?: { id: number; codigo: string; descricao: string; score: number }[];
}

export interface NFeEntradaConferencia {
  id: number;
  nf_entrada_historica: number;
  numero: string;
  serie: string;
  data_emissao: string;
  valor_total: number;
  fornecedor_nome: string;
  fornecedor_cnpj: string;
  status: 'PENDENTE' | 'CONFERIDA' | 'PREPARADA' | 'CANCELADA';
  pedido_compra_id?: number | null;
  pedido_compra_numero?: string;
  divergencias_aceitas: boolean;
  observacao_divergencias?: string;
  preparado_em?: string | null;
  itens: ItemConferenciaNFeEntrada[];
}

export interface NFeSaida {
  id: number;
  numero: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  valor_total: number;
  status: string;
  condicao_pagamento_texto?: string;
  dias_parcelas?: number[];
  quantidade_parcelas?: number;
  vencimentos_finais?: string[];
  titulos_receber?: {
    parcela: number;
    dias: number;
    vencimento: string;
    valor: string;
    status: string;
  }[];
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
  codigo?: string;
  saldo_principal?: number;
  unidade_principal?: string;
  peso_kg?: number | null;
  metros?: number | null;
  barras?: number | null;
  toneladas?: number | null;
  pecas?: number | null;
  chapas?: number | null;
  usa_conversao_dimensional?: boolean;
  alertas?: string[];
}

export interface EstoqueSaldoItem {
  produto_id: number;
  codigo: string;
  descricao: string;
  corrida?: string;
  saldo_principal: string;
  unidade_principal: string;
  peso_kg?: string | null;
  metros?: string | null;
  barras?: string | null;
  toneladas?: string | null;
  usa_conversao_dimensional: boolean;
  tipo_fisico: string;
  alertas: string[];
  quantidade_corridas?: number;
  corridas_resumo?: string[];
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

/** Regime tributário (cadastros Cliente / Fornecedor / Transportadora). */
export const REGIMES_CADASTRO = ['Simples Nacional', 'Lucro Presumido', 'Lucro Real'] as const;

export const TIPOS_CONTA = [
  { value: 'Corrente', label: 'Corrente' },
  { value: 'Poupanca', label: 'Poupança' },
] as const;

export const POLEGADAS = ['1/2"','3/4"','1"','1 1/4"','1 1/2"','2"','2 1/2"','3"','4"','6"','8"','10"','12"'];

export const MATERIAIS = ['Aço Carbono','Aço Inoxidável','Aço Liga','Ferro Fundido','Bronze','Latão'];
