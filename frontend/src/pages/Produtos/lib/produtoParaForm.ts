import type { ModoCodigoProduto, Produto } from '@/types';
import type { ProdutoFormState } from '../types';

/**
 * Produto (payload da API) → ProdutoFormState. Fonte única da conversão: a ficha de
 * Edição hidrata o form com ela e a Visualização usa o mesmo mapeamento para renderizar
 * os componentes da Edição em modo somente-leitura — assim as duas telas não divergem
 * no que cada campo significa.
 */
export function produtoParaFormState(produto: Produto): ProdutoFormState {
  return {
    modo_codigo: (produto.modo_codigo as ModoCodigoProduto) || 'LEGADO',
    familia_id: produto.familia_id ?? null,
    rosca_conexao_id: produto.rosca_conexao_id ?? null,
    schedule_ref_id: produto.schedule_ref_id ?? null,
    polegada_principal_ref_id: produto.polegada_principal_ref_id ?? null,
    polegada_secundaria_ref_id: produto.polegada_secundaria_ref_id ?? null,
    figura: produto.figura ?? '',
    sufixo: produto.sufixo ?? '',
    schedule: produto.schedule ?? '',
    polegada_principal: produto.polegada_principal ?? '',
    polegada_secundaria: produto.polegada_secundaria ?? '',
    descricao: produto.descricao,
    material: produto.material ?? '',
    material_ref: produto.material_ref ?? null,
    tipo_peca: produto.tipo_peca ?? '',
    pressao_nominal: produto.pressao_nominal ?? '',
    norma: produto.norma ?? '',
    conexao: produto.conexao ?? '',
    ncm: produto.ncm ?? '',
    unidade: produto.unidade ?? '',
    ncm_especifico: produto.ncm_especifico ?? '',
    unidade_especifica: produto.unidade_especifica ?? '',
    tipo_controle_unidade: produto.tipo_controle_unidade ?? '',
    tipo_fisico: produto.tipo_fisico ?? '',
    unidade_estoque: produto.unidade_estoque ?? '',
    unidade_venda_padrao: produto.unidade_venda_padrao ?? '',
    unidade_compra_padrao: produto.unidade_compra_padrao ?? '',
    unidade_fiscal: produto.unidade_fiscal ?? '',
    unidades_venda_permitidas: produto.unidades_venda_permitidas ?? [],
    unidades_compra_permitidas: produto.unidades_compra_permitidas ?? [],
    observacoes_conversao: produto.observacoes_conversao ?? '',
    comprimento_padrao_barra_m: produto.comprimento_padrao_barra_m ?? null,
    peso_por_metro_kg: produto.peso_por_metro_kg ?? null,
    peso_por_peca_kg: produto.peso_por_peca_kg ?? null,
    peso_por_chapa_kg: produto.peso_por_chapa_kg ?? null,
    densidade: produto.densidade ?? null,
    usa_conversao_dimensional: !!produto.usa_conversao_dimensional,
    controla_composicao_fisica: !!produto.controla_composicao_fisica,
    exige_certificado_qualidade: !!produto.exige_certificado_qualidade,
    tipo_composicao_fisica: (produto.tipo_composicao_fisica || produto.tipo_composicao_fisica_efetivo || 'BARRA_M') as
      | 'BARRA_M'
      | 'PECA_KG',
    preco_custo: produto.preco_custo ?? 0,
    preco_venda: produto.preco_venda ?? 0,
    estoque_minimo: produto.estoque_minimo ?? 0,
    codigo_completo: produto.codigo_completo ?? '',
    od_mm: produto.od_mm ?? null,
    diametro_interno_mm: produto.diametro_interno_mm ?? null,
    espessura_mm: produto.espessura_mm ?? null,
    comprimento_mm: produto.comprimento_mm ?? null,
    diametro_mostrador_mm: produto.diametro_mostrador_mm ?? null,
    escala: produto.escala ?? '',
    unidade_escala: produto.unidade_escala ?? '',
    fluido: produto.fluido ?? '',
    dim_espessura_mm: produto.dim_espessura_mm ?? null,
    dim_largura_mm: produto.dim_largura_mm ?? null,
    dim_comprimento_mm: produto.dim_comprimento_mm ?? null,
    dim_altura_mm: produto.dim_altura_mm ?? null,
    dim_furo_mm: produto.dim_furo_mm ?? null,
    dim_aba_mm: produto.dim_aba_mm ?? null,
    dim_aba_polegada_ref: produto.dim_aba_polegada_ref ?? null,
    dim_espessura_polegada_ref: produto.dim_espessura_polegada_ref ?? null,
    dimensao_codigo: produto.dimensao_codigo ?? '',
    dimensao_descricao: produto.dimensao_descricao ?? '',
    dimensoes_json: produto.dimensoes_json ?? {},
  };
}
