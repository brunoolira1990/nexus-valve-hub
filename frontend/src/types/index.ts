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
  /** Ambiente NF-e desejado: homologacao | producao */
  nfe_ambiente?: 'homologacao' | 'producao';
  /** Espelha settings.NFE_PRODUCAO_HABILITADA (somente leitura). */
  nfe_producao_habilitada?: boolean;
  certificado_arquivo?: File | string | null;
  certificado_validade?: string | null;
  logotipo?: File | string | null;
  criado_em?: string | null;
  atualizado_em?: string | null;
  /** Só envio; não vem da API (write_only no backend). */
  senha_certificado?: string;
}

export type TipoContatoCliente = 'COMERCIAL' | 'FINANCEIRO' | 'TECNICO' | 'OUTRO';

export interface EnderecoEntregaCliente {
  id?: number;
  identificacao: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  cidade: string;
  uf: string;
  principal: boolean;
}

export interface ContatoCliente {
  id?: number;
  tipo: TipoContatoCliente;
  nome: string;
  telefone: string;
  celular: string;
  email: string;
  principal: boolean;
}

export interface Cliente {
  id: number;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  ie: string;
  ie_isento: boolean;
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
  informacoes_complementares_nfe?: string;
  enderecos_entrega?: EnderecoEntregaCliente[];
  contatos?: ContatoCliente[];
  endereco_fiscal?: {
    consistente?: boolean;
    bloqueio_fiscal?: boolean;
    alertas?: string[];
    pendencias?: string[];
  };
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
  | 'BASE_OD_MM_ESPESSURA'
  | 'BASE_OD_POLEGADA_ESPESSURA'
  | 'BASE_DN_MM'
  | 'BASE_DN_MM_REDUCAO'
  | 'BASE_BITOLA_POLEGADA'
  | 'BASE_OD_MM'
  | 'BASE_OD_MM_REDUCAO'
  | 'BASE_OD_MM_X_ROSCA'
  | 'BASE_ESPIGAO_FLANGE_NPS'
  | 'MANUAL_FABRICANTE';

export type TipoDimensional =
  | 'SIMPLES'
  | 'NPS'
  | 'NPS_SCHEDULE'
  | 'REDUCAO_NPS'
  | 'ROSCA'
  | 'ROSCA_X_ROSCA'
  | 'NPS_X_ROSCA'
  | 'OD_POLEGADA'
  | 'OD_POLEGADA_X_ESPESSURA'
  | 'OD_POLEGADA_X_ROSCA'
  | 'OD_MM'
  | 'DN_MM'
  | 'DN_MM_REDUCAO'
  | 'BITOLA_POLEGADA'
  | 'OD_MM_REDUCAO'
  | 'OD_MM_X_ROSCA'
  | 'OD_MM_X_ESPESSURA'
  | 'OD_MM_X_ESPESSURA_X_COMPRIMENTO'
  | 'CHAPA_MM'
  | 'CHAPA_FURO_MM'
  | 'BARRA_CHATA_MM'
  | 'METALON_MM'
  | 'CANTONEIRA_MM'
  | 'CANTONEIRA_POLEGADA'
  | 'DIMENSIONAL_LIVRE_CONTROLADO'
  | 'PERFIL_RETANGULAR_MM'
  | 'FLANGE'
  | 'ESPIGAO_X_FLANGE'
  | 'VALVULA'
  | 'MANUAL'
  | 'LEGADO';

export type RequisitosProdutoDimensionais = {
  usa_rosca_conexao: boolean;
  usa_schedule: boolean;
  usa_polegada_principal: boolean;
  usa_polegada_secundaria: boolean;
  exige_od_mm: boolean;
  exige_espessura_mm: boolean;
  exige_comprimento_mm: boolean;
  incluir_schedule_na_descricao: boolean;
};

export interface FamiliaProduto {
  id: number;
  codigo_figura: string;
  descricao_base: string;
  tipo_regra_codigo: TipoRegraCodigo;
  categoria_produto?: 'PRODUTO_TECNICO' | 'MATERIAL_DIMENSIONAL' | 'MANUAL_FABRICANTE';
  tipo_dimensional?: TipoDimensional;
  requisitos_produto?: RequisitosProdutoDimensionais;
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
  controla_composicao_fisica?: boolean;
  tipo_composicao_fisica?: string;
  tipo_composicao_fisica_efetivo?: string;
  unidade_base_composicao_fisica?: string;
  observacoes_conversao?: string;
  polegadas_permitidas?: Array<{
    permitida_id?: number;
    /** ID da polegada (FK); mantido como `id` por compatibilidade com o front. */
    id: number;
    polegada_id?: number;
    codigo: string;
    descricao: string;
    tipo_medida?: 'NPS' | 'OD';
    tipo: 'principal' | 'secundaria' | 'ambas';
  }>;
  roscas_permitidas?: Array<{ id: number; codigo: string; descricao: string; padrao_da_familia: boolean }>;
  schedules_permitidos?: Array<{
    permitido_id?: number;
    /** ID do schedule (FK); mantido como `id` por compatibilidade. */
    id: number;
    schedule_id?: number;
    codigo_schedule: string;
    codigo?: string;
    descricao: string;
    aplicacao?: 'CARBONO' | 'INOX' | 'AMBOS' | 'OUTRO';
    padrao_da_familia: boolean;
  }>;
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
  codigo?: string;
  descricao: string;
  aplicacao?: 'CARBONO' | 'INOX' | 'AMBOS' | 'OUTRO';
  ordem?: number | null;
  ativo: boolean;
  observacoes?: string;
}

export interface Polegada {
  id: number;
  tipo_medida?: 'NPS' | 'OD';
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
  material_label?: string | null;
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
  peso_por_metro_kg_efetivo?: number | null;
  comprimento_padrao_barra_m_efetivo?: number | null;
  unidades_venda_permitidas_efetivas?: string[];
  controla_composicao_fisica_efetivo?: boolean;
  controla_composicao_fisica?: boolean;
  tipo_composicao_fisica?: string;
  tipo_composicao_fisica_efetivo?: string;
  unidade_base_composicao_fisica?: string;
  usa_conversao_dimensional_efetivo?: boolean;
  origem_ncm?: 'familia' | 'produto';
  origem_unidade?: 'familia' | 'produto';
  alertas?: string[];
  preco_custo: number;
  preco_venda: number;
  estoque_minimo: number;
  codigo_completo: string;
  od_mm?: number | null;
  espessura_mm?: number | null;
  comprimento_mm?: number | null;
  dim_espessura_mm?: number | null;
  dim_largura_mm?: number | null;
  dim_comprimento_mm?: number | null;
  dim_altura_mm?: number | null;
  dim_furo_mm?: number | null;
  dim_aba_mm?: number | null;
  dim_aba_polegada_ref?: number | null;
  dim_espessura_polegada_ref?: number | null;
  dimensao_codigo?: string;
  dimensao_descricao?: string;
  dimensoes_json?: Record<string, number | string | null>;
}

export interface ProdutoPainelResumoProduto {
  id: number;
  codigo: string;
  descricao: string;
  material: string;
  norma: string;
  polegada: string;
  ncm: string;
}

export interface ProdutoPainelResumoEstoque {
  saldo_fisico: string;
  reservado: string;
  disponivel: string;
}

export interface ProdutoPainelResumoUltimaCompra {
  origem: string;
  fornecedor: string;
  fornecedor_id?: number | null;
  data: string | null;
  valor_unitario: string;
  pedido_compra_id?: number | null;
  pedido_compra_numero?: string | null;
  nf_entrada_id?: number | null;
  nf_entrada_numero?: string | null;
  nf_entrada_historica_id?: number | null;
  conferencia_id?: number | null;
}

export interface ProdutoPainelResumoUltimaVenda {
  origem: string;
  cliente: string;
  cliente_id?: number | null;
  pedido_id?: number | null;
  pedido_numero?: string | null;
  nf: string | null;
  nf_id?: number | null;
  data: string | null;
}

export interface ProdutoPainelResumoUltimaNfEntrada {
  origem: string;
  numero: string;
  nf_entrada_id?: number | null;
  nf_entrada_historica_id?: number | null;
  conferencia_id?: number | null;
  fornecedor: string;
  fornecedor_id?: number | null;
  data: string | null;
  quantidade: string;
  valor_unitario: string;
}

export interface ProdutoPainelResumoUltimaNfSaida {
  numero: string;
  nf_id: number;
  cliente: string;
  cliente_id?: number | null;
  data: string | null;
  quantidade: string;
  valor_unitario: string;
}

export interface ProdutoPainelResumoUltimoCq {
  numero: string;
  certificado_qualidade_id: number;
  cliente: string;
  cliente_id?: number | null;
  data: string | null;
  status: string;
}

export interface ProdutoPainelResumoUltimaCorrida {
  corrida: string;
  corrida_id?: number | null;
  fornecedor: string;
  saldo_atual: string;
  data_recebimento?: string | null;
  origem?: string;
}

export interface ProdutoPainelHistoricoCompra {
  origem: string;
  data: string | null;
  fornecedor: string;
  fornecedor_id?: number | null;
  nf?: string | null;
  pedido_compra_id?: number | null;
  pedido_compra_numero?: string | null;
  nf_entrada_id?: number | null;
  nf_entrada_historica_id?: number | null;
  conferencia_id?: number | null;
  quantidade: string;
  valor_unitario: string;
  valor_total: string;
}

export interface ProdutoPainelHistoricoVenda {
  origem: string;
  data: string | null;
  cliente: string;
  cliente_id?: number | null;
  pedido_id?: number | null;
  pedido_numero?: string | null;
  nf?: string | null;
  nf_id?: number | null;
  quantidade: string;
  valor_unitario: string;
  valor_total: string;
}

export interface ProdutoPainelInteligenciaCompras {
  menor_preco: string;
  maior_preco: string;
  preco_medio: string;
  ultimo_preco: string;
  fornecedor_menor_preco: string;
  fornecedor_maior_preco: string;
  fornecedor_ultimo_preco: string;
  data_ultimo_preco: string | null;
  quantidade_registros: number;
}

export interface ProdutoPainelInteligenciaVendas {
  menor_preco: string;
  maior_preco: string;
  preco_medio: string;
  ultimo_preco: string;
  cliente_menor_preco: string;
  cliente_maior_preco: string;
  cliente_ultimo_preco: string;
  data_ultimo_preco: string | null;
  quantidade_registros: number;
}

export interface ProdutoPainelQualidadeCertificado {
  numero: string;
  certificado_qualidade_id: number;
  cliente: string;
  cliente_id?: number | null;
  data: string | null;
  status: string;
}

export interface ProdutoPainelQualidadeCorrida {
  corrida: string;
  corrida_id: number;
  fornecedor: string;
  fornecedor_id?: number | null;
  data_recebimento: string | null;
  saldo_atual: string;
  nf_entrada: string;
}

export interface ProdutoPainelFiscalNfEntrada {
  origem: string;
  numero: string;
  nf_entrada_id?: number | null;
  nf_entrada_historica_id?: number | null;
  conferencia_id?: number | null;
  fornecedor: string;
  data: string | null;
  quantidade: string;
  valor_unitario: string;
  valor_total: string;
}

export interface ProdutoPainelFiscalNfSaida {
  numero: string;
  nf_id: number;
  cliente: string;
  data: string | null;
  quantidade: string;
  valor_unitario: string;
  valor_total: string;
}

export interface ProdutoPainelResumo {
  produto: ProdutoPainelResumoProduto;
  estoque: ProdutoPainelResumoEstoque;
  ultima_compra: ProdutoPainelResumoUltimaCompra | null;
  ultima_venda: ProdutoPainelResumoUltimaVenda | null;
  ultima_nf_entrada: ProdutoPainelResumoUltimaNfEntrada | null;
  ultima_nf_saida: ProdutoPainelResumoUltimaNfSaida | null;
  ultimo_cq: ProdutoPainelResumoUltimoCq | null;
  ultima_corrida: ProdutoPainelResumoUltimaCorrida | null;
  historico_compras: ProdutoPainelHistoricoCompra[];
  historico_vendas: ProdutoPainelHistoricoVenda[];
  inteligencia_compras: ProdutoPainelInteligenciaCompras | null;
  inteligencia_vendas: ProdutoPainelInteligenciaVendas | null;
  qualidade: {
    certificados: ProdutoPainelQualidadeCertificado[];
    corridas: ProdutoPainelQualidadeCorrida[];
  };
  fiscal: {
    nf_entrada: ProdutoPainelFiscalNfEntrada[];
    nf_saida: ProdutoPainelFiscalNfSaida[];
  };
}

export interface CorridaRastreabilidade {
  id: number;
  codigo: string;
  lote: string | null;
  saldo: number;
  fornecedor_nome: string | null;
  origem_tecnica: string;
  nf_entrada_numero: string | null;
  possui_cf: boolean;
}

export interface CertificadoQualidadeRastreabilidade {
  id: number;
  numero: string;
  cliente_nome: string | null;
  data_emissao: string | null;
  status: string;
  corridas: { id: number; codigo: string }[];
}

export interface CertificadoFornecedorRastreabilidade {
  id: number;
  numero: string;
  fornecedor_nome: string;
  data_emissao: string | null;
  corridas: { id: number; codigo: string }[];
  nf_entrada_referencia: string | null;
}

export interface NFeEntradaRastreabilidade {
  id: number;
  numero: string;
  fornecedor_nome: string;
  data_entrada: string | null;
  corrida_codigo: string | null;
  status: string;
}

export interface NFeSaidaRastreabilidade {
  id: number;
  numero: string;
  cliente_nome: string;
  data_emissao: string | null;
  pedido_numero: string | null;
  corrida_codigo: string | null;
}

export interface ProdutoRastreabilidade {
  corridas: CorridaRastreabilidade[];
  certificados_qualidade: CertificadoQualidadeRastreabilidade[];
  certificados_fornecedor: CertificadoFornecedorRastreabilidade[];
  nfs_entrada: NFeEntradaRastreabilidade[];
  nfs_saida: NFeSaidaRastreabilidade[];
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
export type RastreabilidadeCqStatus = 'COMPLETA' | 'PARCIAL' | 'PENDENTE';

export interface ResumoRastreabilidadeCertificadoQualidade {
  completos: number;
  parciais: number;
  pendentes: number;
  pode_emitir: boolean;
}

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
  rastreabilidade_status?: RastreabilidadeCqStatus;
  rastreabilidade_label?: string;
  rastreabilidade_mensagens?: string[];
  rastreabilidade_avisos?: string[];
  rastreabilidade_motivos?: string[];
  tem_certificado_fornecedor?: boolean;
  certificado_fornecedor_status?: string | null;
  tem_conferencia_origem?: boolean;
  estoque_aplicado_origem?: boolean;
  tem_corrida_lote?: boolean;
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
  resumo_rastreabilidade?: ResumoRastreabilidadeCertificadoQualidade;
  rastreabilidade_resumo_label?: string;
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
  item_conferencia_id?: number | null;
  origem_nfe_item_numero?: number | null;
  origem_vinculada_em?: string | null;
  origem_nfe_numero?: string | null;
  origem_nfe_serie?: string | null;
  origem_display?: string;
  origem_conferencia_status?: string | null;
  origem_produto_vinculado?: boolean;
  pedido_compra_id?: number | null;
  pedido_compra_numero?: string | null;
  item_pedido_compra_id?: number | null;
  item_pedido_resumo?: {
    pedido_numero?: string;
    codigo?: string;
    descricao?: string;
    quantidade?: string;
    unidade?: string;
    valor_unitario?: string;
  } | null;
  produto_pedido_codigo?: string | null;
  produto_pedido_descricao?: string | null;
  quantidade_pedido?: string | null;
  unidade_pedido?: string | null;
  valor_unitario_pedido?: string | null;
  origem_rastreabilidade_completa?: boolean;
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
  produto_vinculado?: boolean;
  produto_match_tipo?: 'vinculado' | 'sem_vinculo' | 'outro_produto' | null;
  aviso_sem_vinculo_produto?: string;
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

export type SeveridadeRegraFiscalEntrada = 'INFORMATIVO' | 'ALERTA' | 'BLOQUEIO';

export type TipoOperacaoFiscalEntrada =
  | 'COMPRA'
  | 'DEVOLUCAO_VENDA'
  | 'DEVOLUCAO_COMPRA'
  | 'REMESSA'
  | 'BONIFICACAO'
  | 'USO_CONSUMO'
  | 'INDUSTRIALIZACAO'
  | 'OUTROS'
  | '';

export type StatusFiscalConferenciaEntrada = 'OK' | 'ALERTA' | 'SEM_REGRA' | 'BLOQUEADO';

export type TipoEscopoFiscalEntrada = 'GERAL' | 'NCM' | 'NCM_PREFIXO' | 'PRODUTO';

export interface CenarioFiscalEntrada {
  id: number;
  nome: string;
  empresa_id?: number | null;
  regime_tributario: string;
  ativo: boolean;
  padrao: boolean;
  observacoes: string;
  total_escopos?: number;
  total_configuracoes?: number;
  escopos?: CenarioFiscalEntradaEscopo[];
  criado_em?: string;
  atualizado_em?: string;
}

export interface CenarioFiscalEntradaEscopo {
  id: number;
  cenario: number;
  tipo_escopo: TipoEscopoFiscalEntrada;
  ncm: string;
  produto_id?: number | null;
  prioridade_escopo: number;
  ativo: boolean;
  configuracoes_count?: number;
  label?: string;
  criado_em?: string;
  atualizado_em?: string;
}

export type StatusConfiguracaoFiscalEntrada = 'CONFIGURADO' | 'INCOMPLETO' | 'SEM_CONFIGURACAO';

export interface ResumoImpostosMatriz {
  icms: string;
  ipi: string;
  pis: string;
  cofins: string;
}

export interface ConfiguracaoMatrizFiscalEntrada {
  id: number;
  uf_origem: string;
  uf_destino: string;
  cfop_origem: string;
  cfop_entrada: string;
  status_configuracao: StatusConfiguracaoFiscalEntrada;
  label_configuracao: string;
  incompleta?: boolean;
  pendencias_fiscais?: string[];
  tem_reforma?: boolean;
  resumo_impostos: ResumoImpostosMatriz;
  efeitos: {
    movimenta_estoque: boolean;
    exige_certificado_fornecedor: boolean;
    permite_credito_fiscal: boolean;
    severidade: SeveridadeRegraFiscalEntrada;
  };
  ativo: boolean;
}

export interface MatrizEscopoFiscalEntrada {
  escopo: {
    id: number;
    tipo_escopo: TipoEscopoFiscalEntrada;
    ncm: string;
    produto_id?: number | null;
    label: string;
  };
  configuracoes: ConfiguracaoMatrizFiscalEntrada[];
  ufs_sem_configuracao: string[];
}

export interface DestinoCopiaConfiguracaoFiscal {
  uf_origem?: string;
  uf_destino?: string;
  cfop_origem?: string;
  cfop_entrada?: string;
}

export interface ResultadoCopiaConfiguracaoFiscal {
  criados: number[];
  atualizados: number[];
  ignorados: Array<{
    destino: DestinoCopiaConfiguracaoFiscal;
    regra_id?: number;
    motivo: string;
  }>;
}

export type TipoEscopoFiscalSaida = 'GERAL' | 'NCM' | 'NCM_PREFIXO' | 'PRODUTO';

export type DestinatarioContribuinteSaida = 'CONTRIBUINTE' | 'NAO_CONTRIBUINTE' | 'QUALQUER';

export type TipoOperacaoFiscalSaida =
  | 'VENDA'
  | 'DEVOLUCAO'
  | 'REMESSA'
  | 'BONIFICACAO'
  | 'INDUSTRIALIZACAO'
  | 'OUTROS'
  | '';

export type StatusConfiguracaoFiscalSaida = 'CONFIGURADO' | 'INCOMPLETO' | 'SEM_CONFIGURACAO';

export interface CenarioFiscalSaida {
  id: number;
  nome: string;
  empresa_id?: number | null;
  regime_tributario: string;
  ativo: boolean;
  padrao: boolean;
  observacoes: string;
  total_escopos?: number;
  total_configuracoes?: number;
  escopos?: CenarioFiscalSaidaEscopo[];
  criado_em?: string;
  atualizado_em?: string;
}

export interface CenarioFiscalSaidaEscopo {
  id: number;
  cenario: number;
  tipo_escopo: TipoEscopoFiscalSaida;
  ncm: string;
  produto_id?: number | null;
  prioridade_escopo: number;
  ativo: boolean;
  configuracoes_count?: number;
  label?: string;
  tem_reforma?: boolean;
  tem_recomendacoes_nfe?: boolean;
  criado_em?: string;
  atualizado_em?: string;
}

export type OrigemRegraFiscalSaida = 'CENARIO_SAIDA' | 'LEGADO' | 'NAO_ENCONTRADA';

export interface BuscaRegraFiscalSaida {
  origem: OrigemRegraFiscalSaida;
  regra_id: number | null;
  regra_legada_id: number | null;
  cfop: string;
  cfop_st: string;
  cst_icms: string;
  aliquota_icms: string;
  cst_ipi: string;
  aliquota_ipi: string;
  cst_pis: string;
  aliquota_pis: string;
  cst_cofins: string;
  aliquota_cofins: string;
  movimenta_estoque: boolean;
  gera_financeiro: boolean;
  deduzir_icms_base_pis?: boolean;
  deduzir_icms_base_cofins?: boolean;
  tem_reforma_configurada?: boolean;
  tem_recomendacoes_nfe?: boolean;
  mensagens: string[];
}

export type StatusComparativoFiscalSaida =
  | 'IGUAL'
  | 'DIVERGENTE'
  | 'CENARIO_NAO_ENCONTRADO'
  | 'LEGADO_NAO_ENCONTRADO'
  | 'AMBOS_NAO_ENCONTRADOS';

export interface LadoComparativoFiscal {
  encontrado: boolean;
  regra_id: number | null;
  cfop: string;
  cfop_st: string;
  cst_icms: string;
  aliquota_icms: string;
  cst_ipi: string;
  aliquota_ipi: string;
  cst_pis: string;
  aliquota_pis: string;
  cst_cofins: string;
  aliquota_cofins: string;
  movimenta_estoque: boolean | null;
  gera_financeiro: boolean | null;
  aliquota_fcp: string;
  aliquota_icms_st: string;
  deduzir_icms_base_pis?: boolean;
  deduzir_icms_base_cofins?: boolean;
}

export interface DivergenciaComparativoFiscal {
  campo: string;
  label: string;
  legado: string;
  cenario: string;
}

export type HomologacaoFiscalStatusProposta =
  | 'NAO_INICIADA'
  | 'EM_ANALISE'
  | 'APROVADA'
  | 'REPROVADA'
  | 'VOLTOU_LEGADO';

export interface ResumoHomologacaoFiscalProposta {
  total_itens: number;
  iguais: number;
  divergentes: number;
  cenario_nao_encontrado: number;
  legado_nao_encontrado: number;
  ambos_nao_encontrados: number;
  itens_ignorados_sem_contexto: number;
  itens_com_deducao_icms_base_pis_cofins: number;
  itens_com_reforma_configurada: number;
  itens_com_recomendacoes_nfe: number;
}

export interface ItemHomologacaoFiscalProposta {
  item_id: number;
  produto_codigo: string;
  produto_descricao: string;
  ncm: string;
  origem_oficial: OrigemRegraFiscalSaida;
  comparativo_status: StatusComparativoFiscalSaida;
  divergencias: DivergenciaComparativoFiscal[];
  legado: LadoComparativoFiscal;
  cenario: LadoComparativoFiscal;
  regra_fiscal_saida_id: number | null;
  regra_fiscal_legada_id: number | null;
  mensagem_regra_fiscal_saida: string;
  deduzir_icms_base_pis: boolean;
  deduzir_icms_base_cofins: boolean;
  tem_reforma_configurada: boolean;
  tem_recomendacoes_nfe: boolean;
  ignorado_sem_contexto?: boolean;
}

export type TipoEventoHomologacaoFiscal =
  | 'INICIADA'
  | 'RECALCULADA'
  | 'APROVADA'
  | 'REPROVADA'
  | 'VOLTOU_LEGADO'
  | 'ALTEROU_CENARIO';

export interface EventoHomologacaoFiscalProposta {
  id: number;
  tipo_evento: TipoEventoHomologacaoFiscal;
  status_resultante: HomologacaoFiscalStatusProposta;
  usar_cenario_fiscal_saida: boolean;
  cenario_fiscal_saida_id: number | null;
  cenario_fiscal_saida_nome: string;
  observacao: string;
  criado_por_nome: string;
  criado_em: string;
  resumo: ResumoHomologacaoFiscalProposta | null;
  itens?: ItemHomologacaoFiscalProposta[];
}

export interface HistoricoHomologacaoFiscalProposta {
  proposta_id: number;
  eventos: EventoHomologacaoFiscalProposta[];
}

export type TipoEventoComercialProposta =
  | 'PROPOSTA_RECUPERADA'
  | 'PEDIDO_GERADO'
  | 'ITEM_CONVERTIDO'
  | 'ITEM_CANCELADO'
  | 'ITEM_MANTIDO_PENDENTE'
  | 'PEDIDO_EXCLUIDO_STATUS_REVERTIDO'
  | 'REPARO_STATUS_COMERCIAL_PEDIDO';

export interface EventoComercialProposta {
  id: number;
  tipo_evento: TipoEventoComercialProposta;
  descricao: string;
  usuario_nome: string;
  criado_em: string;
  dados_json?: Record<string, unknown> | null;
}

export interface HistoricoComercialProposta {
  proposta_id: number;
  eventos: EventoComercialProposta[];
}

export interface UltimoEventoHomologacaoFiscal {
  id: number;
  tipo_evento: TipoEventoHomologacaoFiscal;
  status_resultante: string;
  criado_em: string;
  criado_por_nome: string;
}

export interface HomologacaoFiscalPropostaPayload {
  status: HomologacaoFiscalStatusProposta;
  observacao: string;
  homologacao_fiscal_em: string | null;
  usar_cenario_fiscal_saida: boolean;
  cenario_fiscal_saida_id: number | null;
  resumo: ResumoHomologacaoFiscalProposta;
  itens: ItemHomologacaoFiscalProposta[];
  total_eventos_homologacao?: number;
  ultimo_evento_homologacao?: UltimoEventoHomologacaoFiscal | null;
}

export interface ComparativoFiscalSaida {
  status: StatusComparativoFiscalSaida;
  cenario: LadoComparativoFiscal;
  legado: LadoComparativoFiscal;
  divergencias: DivergenciaComparativoFiscal[];
  mensagens: string[];
  origem_oficial_proposta: string;
  origem_se_flag_cenario_ativa: OrigemRegraFiscalSaida;
}

export interface LadoResumoCobertura {
  encontrado: boolean;
  regra_id: number | null;
  cfop: string;
}

export interface ResumoCoberturaPropostas {
  total_itens: number;
  iguais: number;
  divergentes: number;
  cenario_nao_encontrado: number;
  legado_nao_encontrado: number;
  ambos_nao_encontrados: number;
  percentual_cobertura_cenario: string;
  percentual_iguais_entre_encontrados: string;
  itens_analisados: number;
  itens_ignorados_sem_contexto: number;
}

export interface ItemCoberturaProposta {
  proposta_id: number;
  proposta_numero: string;
  item_id: number;
  produto_id: number | null;
  produto_codigo: string;
  produto_descricao: string;
  ncm: string;
  uf_origem: string;
  uf_destino: string;
  destinatario_contribuinte: string;
  consumidor_final: boolean | null;
  tipo_operacao: string;
  status: StatusComparativoFiscalSaida;
  divergencias: DivergenciaComparativoFiscal[];
  cenario: LadoResumoCobertura;
  legado: LadoResumoCobertura;
}

export interface LacunaCoberturaProposta {
  ncm: string;
  uf_origem: string;
  uf_destino: string;
  destinatario_contribuinte: string;
  consumidor_final: boolean | null;
  tipo_operacao: string;
  quantidade_itens: number;
  status_predominante: StatusComparativoFiscalSaida;
  acao_sugerida: string;
}

export interface CoberturaPropostasFiscalSaida {
  resumo: ResumoCoberturaPropostas;
  itens: ItemCoberturaProposta[];
  lacunas: LacunaCoberturaProposta[];
  filtros_aplicados: Record<string, unknown>;
}

export type StatusChecklistAtivacao = 'PODE_ATIVAR' | 'ATENCAO' | 'NAO_RECOMENDADO';
export type StatusCriterioChecklist = 'OK' | 'ATENCAO' | 'NAO_RECOMENDADO';

export interface ResumoChecklistAtivacao {
  total_itens: number;
  iguais: number;
  divergentes: number;
  cenario_nao_encontrado: number;
  legado_nao_encontrado: number;
  ambos_nao_encontrados: number;
  percentual_cobertura_cenario: string;
  percentual_divergentes: string;
  percentual_sem_cenario: string;
  percentual_iguais_entre_encontrados: string;
  itens_ignorados_sem_contexto: number;
}

export interface CriterioChecklistAtivacao {
  codigo: string;
  label: string;
  status: StatusCriterioChecklist;
  valor: string;
  limite: string;
  mensagem: string;
}

export interface ChecklistAtivacaoCenarioSaida {
  status: StatusChecklistAtivacao;
  label: string;
  resumo: ResumoChecklistAtivacao;
  criterios: CriterioChecklistAtivacao[];
  recomendacoes: string[];
  lacunas_prioritarias: LacunaCoberturaProposta[];
  filtros_aplicados: Record<string, unknown>;
}

export interface ConfiguracaoMatrizFiscalSaida {
  id: number;
  uf_origem: string;
  uf_destino: string;
  cfop_venda: string;
  cfop_venda_st: string;
  destinatario_contribuinte: DestinatarioContribuinteSaida;
  tipo_operacao: string;
  status_configuracao: StatusConfiguracaoFiscalSaida;
  label_configuracao: string;
  resumo_impostos: ResumoImpostosMatriz;
  tem_reforma?: boolean;
  resumo_reforma?: string;
  tem_recomendacoes_nfe?: boolean;
  qtd_recomendacoes_nfe?: number;
  efeitos: {
    movimenta_estoque: boolean;
    gera_financeiro: boolean;
  };
  ativo: boolean;
}

export interface MatrizEscopoFiscalSaida {
  escopo: {
    id: number;
    tipo_escopo: TipoEscopoFiscalSaida;
    ncm: string;
    produto_id?: number | null;
    label: string;
  };
  configuracoes: ConfiguracaoMatrizFiscalSaida[];
  ufs_sem_configuracao: string[];
}

export interface RegraFiscalSaida {
  id: number;
  cenario_id?: number | null;
  escopo_id?: number | null;
  nome: string;
  codigo: string;
  ativo: boolean;
  prioridade: number;
  uf_origem: string;
  uf_destino: string;
  destinatario_contribuinte: DestinatarioContribuinteSaida;
  consumidor_final?: boolean | null;
  cfop_venda: string;
  cfop_venda_st: string;
  tipo_operacao: TipoOperacaoFiscalSaida;
  descricao_cenario: string;
  label_configuracao?: string;
  status_configuracao?: StatusConfiguracaoFiscalSaida;
  resumo_impostos?: ResumoImpostosMatriz;
  cst_icms: string;
  csosn: string;
  modalidade_bc_icms?: string;
  aliquota_icms?: number | string | null;
  reducao_bc_icms?: number | string | null;
  motivo_desoneracao_icms?: string;
  codigo_beneficio_icms?: string;
  icms_st_aplicavel?: boolean | null;
  cst_icms_st?: string;
  aliquota_icms_st?: number | string | null;
  mva_st?: number | string | null;
  reducao_bc_st?: number | string | null;
  difal_aplicavel?: boolean | null;
  aliquota_icms_interestadual?: number | string | null;
  aliquota_icms_interna_destino?: number | string | null;
  fcp_aplicavel?: boolean | null;
  aliquota_fcp?: number | string | null;
  aliquota_fcp_st?: number | string | null;
  reducao_bc_fcp?: number | string | null;
  valor_fcp_unidade?: number | string | null;
  reforma_tributaria?: Record<string, string | number | null> | null;
  cst_ipi: string;
  tipo_calculo_ipi?: string;
  aliquota_ipi?: number | string | null;
  valor_ipi_unidade?: number | string | null;
  enquadramento_ipi?: string;
  cst_pis: string;
  tipo_calculo_pis?: string;
  aliquota_pis?: number | string | null;
  reducao_base_pis?: number | string | null;
  valor_minimo_pis_unidade?: number | string | null;
  aliquota_pis_st?: number | string | null;
  deduzir_icms_base_pis?: boolean;
  cst_cofins: string;
  tipo_calculo_cofins?: string;
  aliquota_cofins?: number | string | null;
  reducao_base_cofins?: number | string | null;
  valor_minimo_cofins_unidade?: number | string | null;
  aliquota_cofins_st?: number | string | null;
  deduzir_icms_base_cofins?: boolean;
  movimenta_estoque: boolean;
  gera_financeiro: boolean;
  informacoes_complementares: string;
  observacoes: string;
  recomendacoes_nfe?: Record<string, boolean> | null;
  criado_em?: string;
  atualizado_em?: string;
}

export interface RegraFiscalEntrada {
  id: number;
  cenario_id?: number | null;
  escopo_id?: number | null;
  label_configuracao?: string;
  incompleta?: boolean;
  pendencias_fiscais?: string[];
  nome: string;
  codigo: string;
  ativo: boolean;
  prioridade: number;
  /** Legado: espelha cfop_origem na transição. */
  cfop: string;
  cfop_origem: string;
  cfop_entrada: string;
  descricao_cenario: string;
  ncm: string;
  ncm_prefixo: boolean;
  uf_origem: string;
  uf_destino: string;
  tipo_operacao_fiscal: TipoOperacaoFiscalEntrada;
  produto_id?: number | null;
  fornecedor_id?: number | null;
  cst_icms_esperado: string;
  csosn_esperado: string;
  cst_pis_esperado: string;
  cst_cofins_esperado: string;
  cst_ipi_esperado: string;
  modalidade_bc_icms?: string;
  aliquota_icms?: number | string | null;
  reducao_bc_icms?: number | string | null;
  motivo_desoneracao_icms?: string;
  codigo_beneficio_icms?: string;
  icms_st_aplicavel?: boolean | null;
  cst_icms_st_esperado?: string;
  aliquota_icms_st?: number | string | null;
  mva_st?: number | string | null;
  reducao_bc_st?: number | string | null;
  fcp_aplicavel?: boolean | null;
  aliquota_fcp?: number | string | null;
  aliquota_fcp_st?: number | string | null;
  reducao_bc_fcp?: number | string | null;
  valor_fcp_unidade?: number | string | null;
  reforma_tributaria?: Record<string, string | number | null> | null;
  tipo_calculo_ipi?: string;
  aliquota_ipi?: number | string | null;
  valor_ipi_unidade?: number | string | null;
  enquadramento_ipi?: string;
  tipo_calculo_pis?: string;
  aliquota_pis?: number | string | null;
  reducao_base_pis?: number | string | null;
  valor_minimo_pis_unidade?: number | string | null;
  aliquota_pis_st?: number | string | null;
  tipo_calculo_cofins?: string;
  aliquota_cofins?: number | string | null;
  reducao_base_cofins?: number | string | null;
  valor_minimo_cofins_unidade?: number | string | null;
  aliquota_cofins_st?: number | string | null;
  movimenta_estoque: boolean;
  exige_certificado_fornecedor: boolean;
  permite_credito_fiscal: boolean;
  severidade: SeveridadeRegraFiscalEntrada;
  mensagem_padrao: string;
  observacoes: string;
  criado_em?: string;
  atualizado_em?: string;
}

export interface ImpostosSnapshotFiscal {
  cst_icms?: string;
  csosn?: string;
  modalidade_bc_icms?: string;
  aliquota_icms?: string;
  reducao_bc_icms?: string;
  motivo_desoneracao_icms?: string;
  codigo_beneficio_icms?: string;
  icms_st_aplicavel?: string;
  cst_icms_st?: string;
  aliquota_icms_st?: string;
  mva_st?: string;
  reducao_bc_st?: string;
  fcp_aplicavel?: string;
  aliquota_fcp?: string;
  aliquota_fcp_st?: string;
  reducao_bc_fcp?: string;
  valor_fcp_unidade?: string;
  cst_ipi?: string;
  tipo_calculo_ipi?: string;
  aliquota_ipi?: string;
  valor_ipi_unidade?: string;
  enquadramento_ipi?: string;
  cst_pis?: string;
  tipo_calculo_pis?: string;
  aliquota_pis?: string;
  reducao_base_pis?: string;
  valor_minimo_pis_unidade?: string;
  aliquota_pis_st?: string;
  cst_cofins?: string;
  tipo_calculo_cofins?: string;
  aliquota_cofins?: string;
  reducao_base_cofins?: string;
  valor_minimo_cofins_unidade?: string;
  aliquota_cofins_st?: string;
}

export interface DivergenciaFiscalEntrada {
  campo: string;
  label: string;
  esperado: string;
  informado: string;
  mensagem: string;
}

export interface ResultadoFiscalEntrada {
  status: StatusFiscalConferenciaEntrada;
  regra_id: number | null;
  regra_nome: string;
  regra_codigo: string;
  descricao_cenario: string;
  regra_score_especificidade?: number;
  regra_prioridade?: number;
  regra_match_motivos?: string[];
  severidade: string;
  mensagens: string[];
  movimenta_estoque: boolean | null;
  exige_certificado_fornecedor: boolean | null;
  permite_credito_fiscal: boolean | null;
  cfop_nf: string;
  cfop_entrada_esperado: string;
  ncm_nf: string;
  cst_icms_nf: string;
  csosn_nf: string;
  cst_pis_nf: string;
  cst_cofins_nf: string;
  cst_ipi_nf: string;
  impostos_nf?: ImpostosSnapshotFiscal;
  impostos_esperados?: ImpostosSnapshotFiscal;
  divergencias?: DivergenciaFiscalEntrada[];
  tem_reforma_configurada?: boolean;
  reforma_tributaria_esperada?: Record<string, string>;
}

export interface ResumoFiscalConferencia {
  total_itens: number;
  ok: number;
  alerta: number;
  sem_regra: number;
  bloqueado: number;
  movimenta_estoque: number;
  exige_certificado_fornecedor: number;
  ignorados: number;
  uf_origem: string;
  uf_destino: string;
}

export type StatusElegibilidadeEstoqueConferencia =
  | 'APTO'
  | 'APTO_COM_ALERTA'
  | 'BLOQUEADO'
  | 'NAO_MOVIMENTA';

export interface ElegibilidadeEstoqueConferencia {
  status: StatusElegibilidadeEstoqueConferencia;
  label: string;
  mensagens: string[];
  motivos: string[];
  movimenta_estoque: boolean | null;
  exige_certificado_fornecedor: boolean;
  tem_certificado_fornecedor: boolean;
  tem_rastreabilidade_tecnica: boolean;
}

export interface ResumoElegibilidadeEstoqueConferencia {
  aptos: number;
  aptos_com_alerta: number;
  bloqueados: number;
  nao_movimentam: number;
}

export interface TributosNfConferencia {
  cst_icms: string;
  csosn: string;
  cst_pis: string;
  cst_cofins: string;
  cst_ipi?: string;
  aliquota_icms?: string;
  aliquota_ipi?: string;
  aliquota_pis?: string;
  aliquota_cofins?: string;
}

export interface ItemProposta {
  id: number;
  produto_id?: number | null;
  /** UI: modo avulso explícito (novo item inicia false). */
  item_avulso?: boolean;
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
  regra_fiscal_origem?: OrigemRegraFiscalSaida;
  regra_fiscal_saida_id?: number | null;
  regra_fiscal_legada_id?: number | null;
  origem_regra_fiscal_saida?: OrigemRegraFiscalSaida;
  mensagem_regra_fiscal_saida?: string;
  pis_cofins_base_deduz_icms?: boolean;
  deduzir_icms_base_pis?: boolean;
  deduzir_icms_base_cofins?: boolean;
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
  status_comercial?: string;
  pedido_venda_id?: number | null;
  pedido_venda_numero?: string;
  item_pedido_venda_gerado_id?: number | null;
  convertido_em?: string | null;
  motivo_cancelamento_item?: string;
  pode_selecionar_para_pedido?: boolean;
}

export type ColaboradorFuncao =
  | 'vendedor'
  | 'comprador'
  | 'fiscal'
  | 'financeiro'
  | 'estoque'
  | 'qualidade'
  | 'administrador';

export interface Usuario {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
}

export interface Colaborador {
  id: number;
  nome: string;
  codigo: string;
  email?: string;
  telefone?: string;
  ativo: boolean;
  usuario_id?: number | null;
  usuario_login?: string;
  usuario_email?: string;
  eh_vendedor: boolean;
  eh_comprador: boolean;
  eh_responsavel_fiscal: boolean;
  eh_responsavel_financeiro: boolean;
  eh_responsavel_estoque: boolean;
  eh_responsavel_qualidade: boolean;
  eh_administrador: boolean;
  observacoes?: string;
  /** Preenchido quando eh_vendedor e há registro Vendedor espelhado. */
  vendedor_id?: number | null;
  criado_em?: string;
  atualizado_em?: string;
  cargo?: string;
  departamento?: string;
  /** sem_usuario | usuario_ativo | usuario_inativo | sem_perfil | superusuario */
  status_acesso?: string;
  acesso_status?: 'SEM_USUARIO' | 'USUARIO_ATIVO' | 'USUARIO_INATIVO' | 'SEM_PERFIL' | 'SUPERUSUARIO';
  acesso_status_label?: string;
  badge_acesso?: string;
  perfil_acesso?: string;
  perfil_acesso_label?: string;
  perfil_sugerido?: string | null;
  perfil_sugerido_label?: string | null;
  usuario_ativo?: boolean;
  usuario_is_staff?: boolean;
  usuario_is_superuser?: boolean;
  usuario_grupos?: string[];
  sem_perfil?: boolean;
  email_tecnico?: boolean;
  pode_criar_usuario?: boolean;
  pode_vincular_usuario?: boolean;
  pode_desativar_acesso?: boolean;
  pode_reenviar_convite?: boolean;
  pode_redefinir_senha?: boolean;
  pode_definir_perfil?: boolean;
  pode_editar_acesso?: boolean;
  motivo_bloqueio_acesso?: string;
  acesso_sistema?: {
    tem_usuario?: boolean;
    usuario_id?: number | null;
    login?: string;
    email?: string;
    ativo?: boolean;
    is_staff?: boolean;
    is_superuser?: boolean;
    perfil_principal?: string;
    grupos?: string[];
    sem_perfil?: boolean;
    email_tecnico?: boolean;
    pode_editar_acesso?: boolean;
    pode_redefinir_senha?: boolean;
    pode_desativar?: boolean;
  };
  perfil_acesso_vinculo?: string;
}

export interface Vendedor {
  id: number;
  nome: string;
  codigo: string;
  ativo: boolean;
  usuario_id?: number | null;
  email?: string;
  telefone?: string;
  observacoes?: string;
  criado_em?: string;
  atualizado_em?: string;
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
  validade_dias?: number | null;
  frete_texto?: string;
  mensagem_comercial?: string;
  observacoes_proposta?: string;
  referencia_cliente?: string;
  /** Texto legado ou espelho do vendedor cadastrado. */
  vendedor: string;
  vendedor_id?: number | null;
  vendedor_nome?: string;
  status: string;
  condicao_pagamento_texto: string;
  prazo_entrega_texto?: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  vencimentos_previstos: string[];
  valor_total: number;
  /** Derivada da empresa emitente (somente leitura na API). */
  uf_origem?: string;
  uf_destino_avulso?: string;
  /** Fluxo comercial: sempre saída (somente leitura na API). */
  operacao_fiscal?: string;
  usar_cenario_fiscal_saida?: boolean;
  cenario_fiscal_saida_id?: number | null;
  cenario_fiscal_saida_nome?: string;
  origem_fiscal_resumo?: string;
  homologacao_fiscal_status?: HomologacaoFiscalStatusProposta;
  homologacao_fiscal_em?: string | null;
  homologacao_fiscal_observacao?: string;
  pedido_venda_id?: number | null;
  pedido_venda_numero?: string;
  pode_converter_em_pedido?: boolean;
  pode_gerar_pedido?: boolean;
  requer_recuperacao?: boolean;
  pedidos_gerados_resumo?: { id: number; numero: string; status: string }[];
  itens_pendentes_conversao?: number;
  recuperada_em?: string | null;
  motivo_recuperacao?: string;
  status_anterior_recuperacao?: string;
  itens: ItemProposta[];
}

export type AcaoItensNaoSelecionados = 'MANTER_PENDENTE' | 'CANCELAR';

export interface GerarPedidoPropostaPayload {
  itens: { proposta_item_id: number }[];
  acao_itens_nao_selecionados: AcaoItensNaoSelecionados;
  observacao?: string;
}

/** Resposta de POST /api/propostas/{id}/converter-pedido/ (Propostas 2.1). */
export interface ConverterPropostaPedidoResponse {
  pedido_id: number;
  numero: string;
  status: string;
  proposta_id: number;
  proposta_status: string;
  itens_criados: number;
  mensagens: string[];
  ja_existia: boolean;
  pedido?: PedidoVenda;
}

export interface RecuperarPropostaResponse {
  proposta_id: number;
  proposta_status: string;
  mensagem: string;
}

export interface ItemPedido {
  id: number;
  produto_id: number;
  produto_nome: string;
  quantidade: number;
  quantidade_recebida?: number;
  saldo_pendente?: number;
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
  /** Alinhado a vProd / vIPI / vST / vDesc / vFrete / vOutro (NF-e). */
  ipi_percentual?: number;
  ipi_valor?: number;
  icms_st_percentual?: number;
  icms_st_valor?: number;
  desconto_valor?: number;
  frete_valor?: number;
  outras_despesas_valor?: number;
  valor_produtos?: number;
  valor_total_item?: number;
  quantidade_faturada?: number;
  quantidade_pedida?: number;
  quantidade_pendente?: number;
  quantidade_disponivel?: number;
  status_item?: 'PENDENTE' | 'PARCIAL' | 'FATURADO' | 'CANCELADO';
}

export interface ResumoFaturamentoItemPedido {
  item_pedido_id: number;
  produto_codigo: string;
  descricao: string;
  quantidade_pedida: string;
  quantidade_faturada: string;
  quantidade_pendente: string;
  quantidade_disponivel: string;
  status_item: string;
  valor_unitario: string;
  valor_pendente: string;
}

export interface DuplicataNfeSaida {
  numero: string;
  vencimento: string;
  vencimento_formatado: string;
  valor: string;
  valor_formatado: string;
}

export interface NFeSaidaListagemResumo {
  titulo: string;
  subtitulo: string;
  fiscal_resumo: {
    badge: string;
    variant: string;
    subtexto: string;
  };
  atendimento_resumo: {
    badges: Array<string | { label: string; variant: string }>;
    ocultos: number;
    vazio_label?: string;
  };
  tem_duplicatas: boolean;
  reforma_tributaria_status: string;
}

export interface NFeSaidaListItem {
  id: number;
  numero: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  valor_total: number;
  status: string;
  status_emissao_sefaz?: string;
  listagem_resumo?: NFeSaidaListagemResumo;
}

export interface NFeReformaTributariaPayload {
  status: string;
  status_label: string;
  config: {
    enabled: boolean;
    modo: string;
    incluir_xml: boolean;
    incluir_danfe: boolean;
    producao_bloqueada: boolean;
  };
  alerta_homologacao: string | null;
  itens: Array<{
    item_id: number;
    aplicavel?: boolean;
    cst?: string;
    classificacao_tributaria?: string;
    cbs?: { valor?: string };
    ibs?: { total?: string };
  }>;
  totais: {
    valor_cbs: string;
    valor_ibs: string;
    valor_imposto_seletivo: string;
  };
}

export interface ResumoFaturamentoPedido {
  pedido_id: number;
  status: string;
  pode_faturar: boolean;
  motivo_bloqueio: string;
  total_itens: number;
  itens_pendentes: number;
  itens_parciais: number;
  itens_faturados: number;
  valor_total_pedido: string;
  valor_faturado: string;
  valor_pendente: string;
  faturamentos_rascunho: {
    faturamento_id: number;
    numero_faturamento?: string;
    status: string;
    observacao: string;
    criado_em: string;
    itens_count: number;
  }[];
  faturamentos_nfe: {
    faturamento_id: number;
    numero_faturamento?: string;
    status: string;
    observacao: string;
    criado_em: string;
    itens_count: number;
    nfe_saida_id: number | null;
    nfe_saida_numero: string;
    nfe_saida_status: string;
    nfe_titulo_exibicao?: string;
    nfe_numero_fiscal?: string;
    nfe_serie_fiscal?: string;
    nfe_status_emissao_sefaz?: string;
    nfe_cstat?: string;
    duplicatas_nfe?: DuplicataNfeSaida[];
    nfe_cancelada_sefaz?: boolean;
    nfe_protocolo_cancelamento?: string;
    nfe_motivo_cancelamento?: string;
    nfe_cancelada_em?: string | null;
    pode_gerar_nova_nfe?: boolean;
    estorno_ja_aplicado?: boolean;
    saldo_liberado_por_cancelamento_nfe?: boolean;
    pode_estornar_pre_autorizacao?: boolean;
    motivo_bloqueio_estorno?: string;
  }[];
  historico_nfe_saida?: HistoricoNfeSaidaPedido[];
  itens: ResumoFaturamentoItemPedido[];
  resumo_atendimento_operacional?: import('@/types/atendimentoOperacional').ResumoAtendimentoOperacional | null;
  inconsistencias?: {
    codigo: string;
    mensagem: string;
    faturamento_id?: string;
    numero_faturamento?: string;
    bloqueia_geracao_nfe?: boolean;
  }[];
  tem_inconsistencia_fiscal?: boolean;
  tem_inconsistencia_bloqueante_nfe?: boolean;
  tem_nfe_fiscal_ativa?: boolean;
  nfe_fiscal_ativa_ids?: number[];
  valor_total_pedido_salvo?: string;
  valor_total_recalculado?: boolean;
}

export interface HistoricoNfeSaidaPedido {
  nfe_saida_id: number;
  numero: string;
  numero_interno?: string;
  titulo_exibicao?: string;
  numero_faturamento?: string;
  numero_fiscal?: string;
  serie_fiscal?: string;
  status_emissao_sefaz?: string;
  status: string;
  status_fiscal_label?: string;
  badge_status?: string;
  data: string;
  faturamento_id: number | null;
  valor_total: string;
  chave_acesso_resumida?: string;
  protocolo_autorizacao?: string;
  protocolo_cancelamento?: string;
  cstat_autorizacao?: string;
  ambiente_emissao?: string;
  ambiente_label?: string;
  papel_fiscal?: 'ativa' | 'historico' | 'pendente' | 'rejeitada';
  mensagem_papel_fiscal?: string;
  vinculo_faturamento_ativo?: boolean;
  cancelada_em: string | null;
  motivo_cancelamento?: string;
  efeitos_autorizacao_aplicados_em: string | null;
  efeitos_cancelamento_aplicados_em?: string | null;
}

export interface GerarNFeSaidaFaturamentoResponse {
  nfe_saida_id: number;
  numero: string;
  status: string;
  pedido_id: number;
  faturamento_id: number;
  itens_criados: number;
  mensagens: string[];
  ja_existia: boolean;
  nfe_saida?: NFeSaida;
}

export interface CriarFaturamentoPedidoResponse {
  faturamento_id: number;
  pedido_id: number;
  status: string;
  itens_criados: number;
  mensagens: string[];
}

export interface ConfirmarFaturamentoPedidoResponse {
  faturamento_id: number;
  pedido_id: number;
  status: string;
  pedido_status: string;
  mensagens: string[];
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
  vendedor?: string;
  vendedor_id?: number | null;
  vendedor_nome?: string;
  prazo_entrega?: string | null;
  prazo_entrega_texto?: string;
  observacoes_comerciais?: string;
  observacoes_internas?: string;
  condicao_pagamento_texto: string;
  dias_parcelas: number[];
  quantidade_parcelas: number;
  vencimentos_previstos: string[];
  valor_total: number;
  proposta_id?: number;
  proposta_numero?: string;
  itens: ItemPedido[];
  resumo_atendimento_operacional?: import('@/types/atendimentoOperacional').ResumoAtendimentoOperacional | null;
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
  prazo_entrega_texto?: string;
  data_prevista_entrega?: string | null;
  resumo_financeiro_pedido?: {
    subtotal_produtos: number;
    total_ipi: number;
    total_icms_st: number;
    total_descontos: number;
    total_frete: number;
    total_outras_despesas: number;
    valor_total_pedido: number;
  };
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

export type NFeEntradaTipoOrigem = 'MANUAL' | 'ENTRADA_PROPRIA_IMPORTADA';

export type NFeEntradaStatusOperacional = 'RASCUNHO' | 'IMPORTADA_PENDENTE_CONFERENCIA';

export type NFeEntradaItemJsonRaw = import('@/lib/nfeEntradaItensJson').NFeEntradaItemJsonRaw;

export interface NFeEntrada {
  id: number;
  numero: string;
  fornecedor_id?: number | null;
  fornecedor_nome: string;
  fornecedor_cnpj?: string;
  destinatario_nome?: string;
  data: string;
  valor_total: number;
  serie?: string;
  chave_acesso?: string;
  tipo_origem?: NFeEntradaTipoOrigem;
  tipo_origem_label?: string;
  status_operacional?: NFeEntradaStatusOperacional;
  status_operacional_label?: string;
  pedido_compra_id?: number;
  cte_id?: number;
  importado_em?: string | null;
  /** Itens operacionais vinculados (relacional) — vazio para entrada própria importada. */
  itens: ItemNFe[];
  /** Itens parseados do XML importado (somente leitura). */
  itens_json?: NFeEntradaItemJsonRaw[];
}

export type NFeEntradaPropriaImportResultado = {
  importadas: {
    arquivo: string;
    id: number;
    chave_acesso: string;
    numero: string;
    serie: string;
    tipo_origem: string;
    status_operacional: string;
  }[];
  duplicadas: { arquivo: string; chave_acesso: string; mensagem: string }[];
  erros: import('@/utils/nfeXmlImportDiagnostico').NFeXmlImportFalhaApi[];
  resumo: { total_arquivos: number; importadas: number; duplicadas: number; erros: number };
};

export type StatusItemConferenciaNFeEntrada =
  | 'PENDENTE_PRODUTO'
  | 'PRODUTO_VINCULADO'
  | 'CONFERIDO'
  | 'DIVERGENTE'
  | 'IGNORADO';

export interface CorridaSplitConferencia {
  id?: number;
  ordem: number;
  corrida: string;
  lote: string;
  quantidade: string;
}

export interface EquivalenciaEntradaConferencia {
  id?: number;
  ordem: number;
  metros?: string;
  barras?: string;
  qtd_barras?: number | string;
  comprimento_unitario_m?: string;
  peso_kg?: string;
  peso_real_kg?: string;
  peso_por_metro_utilizado?: string;
}

export interface EstoqueBarraConferencia {
  id: number;
  codigo_interno_barra: string;
  tipo_composicao?: string;
  unidade_base: string;
  quantidade_original?: string;
  saldo: string;
  comprimento_original_m?: string | null;
  saldo_m?: string | null;
  status: string;
  origem: string;
  nf_numero?: string;
  metadata?: Record<string, unknown>;
  criado_em?: string;
}

export interface ItemConferenciaNFeEntrada {
  id: number;
  item_nfe_historico: number;
  produto_id?: number | null;
  produto_nome?: string;
  produto_sugerido?: {
    id: number;
    codigo: string;
    descricao: string;
    codigo_fornecedor?: string;
    descricao_fornecedor?: string;
  } | null;
  item_pedido_compra_id?: number | null;
  status: StatusItemConferenciaNFeEntrada;
  motivo_ignorado?: string;
  observacao?: string;
  corrida?: string;
  lote?: string;
  corridas_split?: CorridaSplitConferencia[];
  equivalencias?: EquivalenciaEntradaConferencia[];
  estoque_barras?: EstoqueBarraConferencia[];
  controla_composicao_fisica_efetivo?: boolean;
  tipo_composicao_fisica_efetivo?: string;
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
  conversao_estoque_auditoria?: Record<string, unknown>;
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
  item_pedido_resumo?: {
    pedido_numero?: string;
    produto_id?: number;
    codigo?: string;
    descricao?: string;
    quantidade?: string;
    unidade?: string;
    valor_unitario?: string;
  } | null;
  pedido_numero?: string;
  item_pedido_produto_codigo?: string;
  item_pedido_produto_descricao?: string;
  item_pedido_quantidade?: string;
  item_pedido_unidade?: string;
  item_pedido_valor_unitario?: string;
  sugestoes_item_pedido?: SugestaoItemPedidoConferencia[];
  tributos_nf?: TributosNfConferencia;
  resultado_fiscal?: ResultadoFiscalEntrada;
  elegibilidade_estoque?: ElegibilidadeEstoqueConferencia;
  quantidade_alocada_atendimento?: string;
  quantidade_disponivel_atendimento?: string;
  vinculos_atendimento?: {
    linha_id: number;
    atendimento_id: number;
    numero_nf_saida: string;
    cliente_nome: string;
    quantidade: string;
    status_atendimento: string;
  }[];
}

export interface SugestaoItemPedidoConferencia {
  id: number;
  produto_codigo: string;
  descricao: string;
  quantidade: number;
  unidade: string;
  valor_unitario: number;
  score: number;
  motivos: string[];
}

export interface ResumoPedidoConferenciaTotais {
  itens_pedido: number;
  itens_nf: number;
  vinculados: number;
  faltantes: number;
  extras: number;
  itens_parciais: number;
  itens_excedentes: number;
  itens_completos: number;
  itens_duplicados_na_nf: number;
  itens_pendentes_global: number;
  itens_parciais_global: number;
  itens_completos_global: number;
  itens_excedentes_global: number;
}

export type StatusQuantitativoPedidoConferencia =
  | 'nao_vinculado'
  | 'parcial'
  | 'completo'
  | 'excedente';

export interface ResumoQuantitativoLinhaVinculada {
  id: number;
  n_item: number;
}

export interface ResumoQuantitativoItemPedido {
  item_pedido_id: number;
  produto_codigo: string;
  descricao: string;
  quantidade_pedido: number;
  quantidade_nf_vinculada: number;
  saldo_na_nf: number;
  status_quantitativo: StatusQuantitativoPedidoConferencia;
  linhas_vinculadas: ResumoQuantitativoLinhaVinculada[];
  alertas: string[];
}

export interface ResumoPedidoItemPedidoSemNf {
  id: number;
  produto_codigo: string;
  descricao: string;
  quantidade: number;
  unidade: string;
  valor_unitario: number;
}

export interface ResumoPedidoItemNfSemPedido {
  id: number;
  n_item: number;
  codigo_fornecedor: string;
  descricao_fornecedor: string;
  quantidade: number;
  unidade: string;
  valor_unitario: number;
}

export type StatusSaldoGlobalPedido = 'pendente' | 'parcial' | 'completo' | 'excedente';

export interface ConferenciaRelacionadaSaldo {
  conferencia_id: number;
  nf_numero: string;
  nf_serie: string;
  quantidade: number;
  atual: boolean;
}

export interface SaldoPedidoGlobalItem {
  item_pedido_id: number;
  produto_codigo: string;
  descricao: string;
  quantidade_pedido: number;
  quantidade_nf_atual: number;
  quantidade_outras_nfs: number;
  quantidade_total_conferida: number;
  saldo_pedido: number;
  status_saldo: StatusSaldoGlobalPedido;
  conferencias_relacionadas: ConferenciaRelacionadaSaldo[];
}

export interface ResumoPedidoConferencia {
  pedido_selecionado: boolean;
  mensagem: string;
  totais: ResumoPedidoConferenciaTotais;
  itens_pedido_sem_nf: ResumoPedidoItemPedidoSemNf[];
  itens_nf_sem_pedido: ResumoPedidoItemNfSemPedido[];
  resumo_quantitativo: ResumoQuantitativoItemPedido[];
  saldo_pedido_global: SaldoPedidoGlobalItem[];
}

export interface FornecedorEntradaStatus {
  status: 'vinculado' | 'encontrado_unico' | 'nao_encontrado' | 'duplicidade' | 'sem_cnpj';
  fornecedor_id?: number | null;
  fornecedor_nome?: string;
  fornecedor_cnpj?: string;
  cnpj_documento?: string;
  candidatos?: Array<{ id: number; razao_social: string; cnpj: string; ativo: boolean }>;
  mensagem?: string;
  vinculo_automatico?: boolean;
  identificado?: boolean;
  pode_cadastrar?: boolean;
  pode_vincular_manual?: boolean;
  sugestao_cadastro?: {
    razao_social?: string;
    nome_fantasia?: string;
    cnpj?: string;
    ie?: string;
    logradouro?: string;
    numero?: string;
    complemento?: string;
    bairro?: string;
    cidade?: string;
    uf?: string;
    cep?: string;
    ativo?: boolean;
  };
}

export interface NFeEntradaConferencia {
  id: number;
  nf_entrada_historica: number;
  numero: string;
  serie: string;
  data_emissao: string;
  data_entrada?: string | null;
  valor_total: number;
  fornecedor_nome: string;
  fornecedor_cnpj: string;
  fornecedor_id?: number | null;
  fornecedor?: FornecedorEntradaStatus | null;
  status: 'PENDENTE' | 'CONFERIDA' | 'PREPARADA' | 'CANCELADA';
  pedido_compra_id?: number | null;
  pedido_compra_numero?: string;
  resumo_pedido?: ResumoPedidoConferencia;
  resumo_fiscal?: ResumoFiscalConferencia;
  resumo_elegibilidade_estoque?: ResumoElegibilidadeEstoqueConferencia;
  equivalencias?: import('@/lib/conferenciaEquivalencia').EquivalenciasConferenciaPayload;
  divergencias_aceitas: boolean;
  observacao_divergencias?: string;
  preparado_em?: string | null;
  estoque_aplicado_em?: string | null;
  estoque_aplicado_observacao?: string;
  pedido_baixa_aplicado_em?: string | null;
  chave_acesso?: string;
  financeiro?: {
    financeiro_gerado?: boolean;
    pode_gerar_contas_pagar?: boolean;
    motivo_bloqueio_financeiro?: string;
    possui_pendencias_operacionais?: boolean;
    pode_gerar_com_pendencias?: boolean;
    aviso_pendencias_operacionais?: string;
    motivos_pendencias_operacionais?: string[];
    contas_pagar_vinculadas?: Array<{ id: number; numero: string; status?: string; cancelado?: boolean }>;
    nfe_entrada_cancelada_com_financeiro?: boolean;
  };
  itens: ItemConferenciaNFeEntrada[];
}

export interface EstoqueBarraAplicadaConferencia {
  estoque_barra_id: number;
  codigo_interno_barra: string;
  ordem: number;
  sequencia_grupo?: number;
  tipo_composicao?: string;
  unidade_base?: string;
  quantidade_original?: string;
  saldo: string;
  comprimento_original_m?: string | null;
  saldo_m?: string | null;
  status: string;
}

export interface ItemAplicadoEstoqueConferencia {
  item_conferencia_id: number;
  produto_id: number;
  corrida: string;
  lote: string;
  quantidade: string;
  estoque_corrida_id: number;
  saldo_anterior: string;
  saldo_novo: string;
  split_ordem?: number;
  estoque_barras?: EstoqueBarraAplicadaConferencia[];
}

export interface ItemIgnoradoAplicacaoEstoque {
  item_conferencia_id: number;
  motivo: string;
}

export interface PendenciaAplicacaoEstoque {
  item_conferencia_id: number | null;
  motivo: string;
}

export interface ResultadoAplicacaoEstoque {
  aplicado: boolean;
  conferencia_id: number;
  itens_aplicados: ItemAplicadoEstoqueConferencia[];
  itens_ignorados: ItemIgnoradoAplicacaoEstoque[];
  pendencias: PendenciaAplicacaoEstoque[];
  alertas: string[];
  pedido_compra_baixa?: {
    aplicado?: boolean;
    ja_baixado?: boolean;
    mensagem?: string;
    pedido_compra_status?: string;
    itens_baixados?: Array<{ item_pedido_compra_id: number; quantidade_baixada: string }>;
  };
  conferencia?: NFeEntradaConferencia;
  detail?: string;
}

export type ModoAtendimentoEstoqueNFeSaida = 'IMEDIATO' | 'ANTECIPADO';

export interface ResumoAtendimentoEstoqueNFeSaida {
  quantidade_comprometida_total: string;
  quantidade_atendida_total: string;
  quantidade_pendente_total: string;
  status_atendimento_estoque: string;
  total_atendimentos_ativos: number;
}

export type StatusAtendimentoEstoque = 'PENDENTE' | 'PARCIAL' | 'ATENDIDO' | 'CANCELADO';

export interface AtendimentoEstoqueItem {
  id: number;
  status: StatusAtendimentoEstoque;
  produto_id: number;
  produto_codigo: string;
  produto_descricao: string;
  quantidade_comprometida: string;
  quantidade_atendida: string;
  quantidade_pendente: string;
  unidade: string;
  nf_saida_id: number;
  numero_nf_saida: string;
  cliente_id: number | null;
  cliente_nome: string;
  criado_em: string;
  dias_em_aberto: number;
  estoque_fisico_aplicado: boolean;
}

export interface SaldoConsolidadoProduto {
  produto_id: number;
  produto_codigo: string;
  produto_descricao: string;
  saldo_fisico: string;
  quantidade_comprometida: string;
  quantidade_pendente_atendimento: string;
  quantidade_atendida_sem_fisico: string;
  saldo_disponivel: string;
  alertas: string[];
}

export interface NFeSaida {
  id: number;
  numero: string;
  cliente_id: number;
  cliente_nome: string;
  data: string;
  valor_total: number;
  modo_atendimento_estoque?: ModoAtendimentoEstoqueNFeSaida;
  modo_atendimento_estoque_display?: string;
  resumo_atendimento_estoque?: ResumoAtendimentoEstoqueNFeSaida | null;
  resumo_atendimento_operacional?: import('@/types/atendimentoOperacional').ResumoAtendimentoOperacional | null;
  status: string;
  status_conferencia?: string;
  status_conferencia_display?: string;
  resumo_emissao_sefaz?: import('@/lib/nfeSaidaUi').ResumoEmissaoSefazNfe | null;
  status_emissao_sefaz?: string;
  apresentacao?: import('@/lib/nfeSaidaUi').NFeSaidaApresentacao | null;
  listagem_resumo?: NFeSaidaListagemResumo;
  duplicatas_nfe?: DuplicataNfeSaida[];
  reforma_tributaria?: NFeReformaTributariaPayload | null;
  conferencia_validada_em?: string | null;
  conferencia_marcada_pronta_em?: string | null;
  conferencia_ultima_mensagem?: string;
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
  pedido_venda_numero?: string;
  faturamento_pedido_venda_id?: number | null;
  observacao_origem?: string;
  origem_comercial_travada?: boolean;
  dados_complementares_editaveis?: boolean;
  itens_comerciais_editaveis?: boolean;
  transportadora_id?: number | null;
  transportadora_nome?: string;
  modalidade_frete?: string;
  valor_frete?: number;
  quantidade_volumes?: number;
  peso_bruto?: number;
  peso_liquido?: number;
  observacoes_nfe?: string;
  informacoes_adicionais?: string;
  financeiro_gerado?: boolean;
  pode_gerar_contas_receber?: boolean;
  motivo_bloqueio_financeiro?: string;
  contas_receber_vinculadas?: Array<{ id: number; numero: string; status: string; cancelado: boolean }>;
  nfe_cancelada_com_financeiro?: boolean;
  itens: ItemNFe[];
}

export interface CTeEntrada {
  id: number;
  cte_historico_id?: number;
  numero: string;
  serie?: string;
  chave_acesso?: string;
  transportadora_id?: number;
  transportadora_nome: string;
  tomador_id?: number;
  tomador_nome: string;
  valor_frete: number;
  data: string;
  status_conferencia?: string;
  apto_operacional?: boolean;
  classificacao_dfe?: import('@/components/fiscal/DfeClassificacaoBadges').ClassificacaoDfe;
  nfe_ids?: number[];
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

export interface ApuracaoFiscalFiltros {
  empresa_id: number | null;
  data_inicio: string;
  data_fim: string;
  tipo: string;
  fonte?: 'TODOS' | 'OPERACIONAIS' | 'HISTORICOS';
  status: string | null;
  cliente_id: number | null;
  fornecedor_id: number | null;
  cfop: string | null;
  ncm: string | null;
  modelo_documento: string | null;
  incluir_canceladas: boolean;
}

export interface ApuracaoFiscalAcumulo {
  quantidade_notas: number;
  quantidade_itens: number;
  valor_documentos: number;
  valor_produtos: number;
  base_icms: number;
  valor_icms: number;
  base_ipi: number;
  valor_ipi: number;
  base_pis: number;
  valor_pis: number;
  base_cofins: number;
  valor_cofins: number;
}

export interface ApuracaoFiscalAlerta {
  codigo: string;
  severidade: string;
  mensagem: string;
  documento_tipo?: string | null;
  documento_id?: number | null;
  item_id?: number | null;
  acao_sugerida?: string | null;
}

/** Indicadores pré-SPED EFD ICMS/IPI (backend `montar_base_efd_icms_ipi`). */
export interface ApuracaoEfdIcmsIpiIndicadores {
  notas_mapeaveis_c100?: number;
  notas_com_campos_faltantes_c100?: number;
  itens_mapeaveis_c170?: number;
  itens_cadastro_participante_0150_pendentes?: number;
  produtos_cadastro_0200_pendentes?: number;
  agrupamentos_possiveis_c190?: number;
}

export interface ApuracaoEfdIcmsIpi {
  registros_planejados?: Record<string, string[]>;
  indicadores?: ApuracaoEfdIcmsIpiIndicadores;
  alertas?: string[];
  txt_oficial?: boolean;
  observacao?: string;
}

/** Indicadores pré-SPED Contribuições (backend `montar_base_efd_contribuicoes`). */
export interface ApuracaoEfdContribIndicadores {
  notas_com_totais_pis_cofins_documento?: number;
  itens_com_cst_pis?: number;
  itens_com_cst_cofins?: number;
  itens_com_base_pis?: number;
  itens_com_base_cofins?: number;
  creditos_entrada_possiveis?: number;
  debitos_saida_possiveis?: number;
}

export interface ApuracaoEfdContribuicoes {
  registros_planejados?: Record<string, string[]>;
  indicadores?: ApuracaoEfdContribIndicadores;
  alertas?: string[];
  txt_oficial?: boolean;
  observacao?: string;
}

/** Bloco de totais CBS/IBS/IS (sem recursão por_documento). */
export type ApuracaoReformaDetalhe = Omit<ApuracaoReformaTributaria, 'por_documento'>;

/** Totais reforma (CBS/IBS/IS) serializados pelo backend. */
export interface ApuracaoReformaTributaria {
  base_cbs?: number;
  aliquota_cbs?: number | null;
  valor_cbs?: number;
  base_ibs?: number;
  aliquota_ibs_uf?: number | null;
  valor_ibs_uf?: number;
  aliquota_ibs_municipio?: number | null;
  valor_ibs_municipio?: number;
  valor_ibs_total?: number;
  base_is?: number;
  aliquota_is?: number | null;
  valor_is?: number;
  cst_reforma?: string | null;
  classificacao_tributaria?: string | null;
  cclass_trib?: string | null;
  notas_com_reforma_e_outros_json?: number;
  itens_com_tags_nao_mapeadas_imposto?: number;
  itens_com_tags_ibscbs?: number;
  itens_com_valores_ibscbs?: number;
  notas_com_ibscbstot?: number;
  notas_tags_ibscbs_zeradas?: number;
  cte_com_tags_ibscbs?: number;
  cte_com_valores_ibscbs?: number;
  por_documento?: {
    entrada?: ApuracaoReformaDetalhe;
    saida?: ApuracaoReformaDetalhe;
    cte?: ApuracaoReformaDetalhe;
  };
}

export interface ApuracaoDiagnostico {
  models_utilizados?: string[];
  campos_fiscais_xml?: string[];
  campos_ausentes_sped_reforma?: string[];
  impacto?: string;
}

/** Contagens de candidatos à apuração (após filtros) e referência sem filtro de empresa. */
export interface ApuracaoFiscalFontes {
  saidas_historicas_candidatas?: number;
  entradas_historicas_candidatas?: number;
  saidas_operacionais_candidatas?: number;
  entradas_operacionais_candidatas?: number;
  saidas_historicas_periodo_sem_filtro_empresa?: number;
  entradas_historicas_periodo_sem_filtro_empresa?: number;
  candidatas_aplicaveis_tipo?: number;
  ctes_historicos_escaneados_reforma?: number;
}

/** Contagens progressivas NF histórica + metadados dos campos usados na query. */
export interface ApuracaoDiagnosticoFontes {
  saidas_historicas_total_banco?: number;
  saidas_historicas_no_periodo?: number;
  saidas_historicas_apos_empresa?: number;
  saidas_historicas_apos_status?: number;
  saidas_historicas_apos_canceladas?: number;
  saidas_historicas_incluidas?: number;
  campo_data_usado?: string;
  campo_valor_usado?: string;
  campo_status_usado?: string;
  campo_empresa_usado?: string;
  campo_cancelada_usado?: string;
  entradas_historicas_total_banco?: number;
  entradas_historicas_no_periodo?: number;
  entradas_historicas_apos_empresa?: number;
  entradas_historicas_apos_status?: number;
  entradas_historicas_incluidas?: number;
  entrada_campo_data_usado?: string;
  entrada_campo_valor_usado?: string;
  entrada_campo_empresa_usado?: string;
}

export interface ApuracaoDiagnosticoReformaLado {
  valor_cbs?: number;
  valor_ibs_total?: number;
  valor_ibs_uf?: number;
  valor_ibs_municipio?: number;
  base_cbs?: number;
  itens_com_tags_ibscbs?: number;
  itens_com_valores_ibscbs?: number;
  notas_com_ibscbstot?: number;
}

export interface ApuracaoDiagnosticoReforma {
  candidatas_entrada_historica?: number;
  candidatas_saida_historica?: number;
  entrada?: ApuracaoDiagnosticoReformaLado;
  saida?: ApuracaoDiagnosticoReformaLado;
  cte?: ApuracaoDiagnosticoReformaLado;
  consolidado?: ApuracaoDiagnosticoReformaLado;
}

export interface ApuracaoFiscalPayload {
  meta: {
    versao_api_apuracao: string;
    pre_validacao: boolean;
    sped_txt_oficial: boolean;
    calculo: string;
    parametros_fiscais_futuros: Record<string, unknown>;
  };
  filtros: ApuracaoFiscalFiltros;
  fontes?: ApuracaoFiscalFontes;
  diagnostico_fontes?: ApuracaoDiagnosticoFontes;
  diagnostico_reforma?: ApuracaoDiagnosticoReforma;
  cards: Record<string, number>;
  resumo: {
    entrada: ApuracaoFiscalAcumulo;
    saida: ApuracaoFiscalAcumulo;
    saldo_gerencial_saida_menos_entrada: Record<string, number>;
  };
  icms_ipi: { entrada: ApuracaoFiscalAcumulo; saida: ApuracaoFiscalAcumulo; comparativo_documento: { observacao: string } };
  pis_cofins: { entrada: ApuracaoFiscalAcumulo; saida: ApuracaoFiscalAcumulo };
  reforma_tributaria: ApuracaoReformaTributaria;
  efd_icms_ipi: ApuracaoEfdIcmsIpi;
  efd_contribuicoes: ApuracaoEfdContribuicoes;
  agrupamentos: Record<string, Array<{ chave: string } & ApuracaoFiscalAcumulo>>;
  alertas: ApuracaoFiscalAlerta[];
  diagnostico: ApuracaoDiagnostico;
}

/** @deprecated legado mes/ano — usar ApuracaoFiscalPayload */
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
