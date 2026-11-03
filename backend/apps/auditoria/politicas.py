"""Allowlists e classificação de campos para o MVP de auditoria."""

from __future__ import annotations

# Campos com valor antes/depois permitido (não sensíveis).
CLIENTE_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'razao_social',
        'nome_fantasia',
        'ie',
        'ie_isento',
        'inscricao_municipal',
        'suframa',
        'limite_credito',
        'condicao_pagamento_texto',
        'quantidade_parcelas',
        'bloqueado',
        'ativo',
        'vendedor_padrao',
        'regime_tributario',
        'cnae',
        'transportadora_padrao_id',
        'ddd',
        'tipo_conta',
    }
)

# Campos na allowlist, mas sem valor bruto (somente {sensivel, alterado}).
CLIENTE_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {
        'cnpj',
        'email',
        'email_nf',
        'telefone',
        'telefone_alternativo',
        'celular',
        'contato_responsavel',
        'logradouro',
        'numero',
        'complemento',
        'bairro',
        'cidade',
        'uf',
        'cep',
        'observacoes',
        'informacoes_complementares_nfe',
        'integracao_texto',
        'banco',
        'agencia',
        'conta',
    }
)

CLIENTE_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        'dias_parcelas',
        'contatos',
        'enderecos_entrega',
        'endereco_fiscal',
        'transportadora_padrao',
    }
)

CLIENTE_ALLOWLIST: frozenset[str] = CLIENTE_CAMPOS_VALOR | CLIENTE_CAMPOS_MASCARADOS

# Fornecedor: mesma separação do cliente — identidade e condição de pagamento têm
# valor; documentos, contato, endereço e dados bancários ficam mascarados.
FORNECEDOR_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'razao_social',
        'nome_fantasia',
        'ie',
        'inscricao_municipal',
        'suframa',
        'condicao_pagamento_texto',
        'quantidade_parcelas',
        'prazo_entrega',
        'transportadora_padrao_id',
        'ativo',
        'ddd',
        'tipo_conta',
        'cnae',
        'regime_tributario',
    }
)

FORNECEDOR_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {
        'cnpj',
        'email',
        'email_nf',
        'telefone',
        'telefone_alternativo',
        'celular',
        'contato_responsavel',
        'logradouro',
        'numero',
        'complemento',
        'bairro',
        'cidade',
        'uf',
        'cep',
        'observacoes',
        'integracao_texto',
        'banco',
        'agencia',
        'conta',
    }
)

FORNECEDOR_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        # Derivada de condicao_pagamento_texto no validate(); duplicaria o diff.
        'dias_parcelas',
        'transportadora_padrao',
    }
)

FORNECEDOR_ALLOWLIST: frozenset[str] = FORNECEDOR_CAMPOS_VALOR | FORNECEDOR_CAMPOS_MASCARADOS

# Transportadora: além da identidade fiscal, a tabela de frete (placa e R$ km) tem valor.
TRANSPORTADORA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'razao_social',
        'nome_fantasia',
        'ie',
        'inscricao_municipal',
        'suframa',
        'placa_padrao',
        'uf_placa',
        'valor_km',
        'ativo',
        'ddd',
        'tipo_conta',
        'cnae',
        'regime_tributario',
    }
)

TRANSPORTADORA_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {
        'cnpj',
        'email',
        'email_nf',
        'telefone',
        'celular',
        'contato',
        'logradouro',
        'numero',
        'complemento',
        'bairro',
        'cidade',
        'uf',
        'cep',
        'observacoes',
        'integracao_texto',
        'banco',
        'agencia',
        'conta',
    }
)

TRANSPORTADORA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset({'id'})

TRANSPORTADORA_ALLOWLIST: frozenset[str] = (
    TRANSPORTADORA_CAMPOS_VALOR | TRANSPORTADORA_CAMPOS_MASCARADOS
)

PRODUTO_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'codigo_completo',
        'descricao',
        'unidade',
        'unidade_especifica',
        'ncm',
        'ncm_especifico',
        'modo_codigo',
        'figura',
        'sufixo',
        'schedule',
        'polegada_principal',
        'polegada_secundaria',
        'material',
        'tipo_peca',
        'pressao_nominal',
        'norma',
        'conexao',
        'familia_id',
        'tipo_fisico',
        'tipo_controle_unidade',
        'unidade_estoque',
        'unidade_venda_padrao',
        'unidade_compra_padrao',
        'unidade_fiscal',
        'dimensao_codigo',
        'dimensao_descricao',
    }
)

PRODUTO_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {
        'preco_custo',
        'preco_venda',
    }
)

PRODUTO_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        'estoque_minimo',
        'dimensoes_json',
        'od_mm',
        'espessura_mm',
        'comprimento_mm',
        'dim_espessura_mm',
        'dim_largura_mm',
        'dim_comprimento_mm',
        'dim_altura_mm',
        'dim_furo_mm',
        'dim_aba_mm',
        'peso_por_metro_kg',
        'peso_por_peca_kg',
        'peso_por_chapa_kg',
        'densidade',
        'comprimento_padrao_barra_m',
        'unidades_venda_permitidas',
        'unidades_compra_permitidas',
        'observacoes_conversao',
        'usa_conversao_dimensional',
        'controla_composicao_fisica',
        'tipo_composicao_fisica',
        'familia',
        'rosca_conexao',
        'rosca_conexao_id',
        'schedule_ref',
        'schedule_ref_id',
        'polegada_principal_ref',
        'polegada_principal_ref_id',
        'polegada_secundaria_ref',
        'polegada_secundaria_ref_id',
        'dim_aba_polegada_ref',
        'dim_aba_polegada_ref_id',
        'dim_espessura_polegada_ref',
        'dim_espessura_polegada_ref_id',
    }
)

PRODUTO_ALLOWLIST: frozenset[str] = PRODUTO_CAMPOS_VALOR | PRODUTO_CAMPOS_MASCARADOS

# Família/figura: o molde do código e a classificação técnica herdada pelo produto.
FAMILIA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'codigo_figura',
        'descricao_base',
        'tipo_regra_codigo',
        'categoria_produto',
        'tipo_dimensional',
        'separador_base_medidas',
        'ncm_padrao_id',
        'material_base_ref_id',
        'unidade_padrao',
        'material_base',
        'pressao_base',
        'norma_base',
        'conexao_base',
        'tipo_peca',
        'material_vedacao',
        'ativo',
        'tipo_fisico',
        'tipo_controle_unidade',
        'unidade_estoque_padrao',
        'unidade_venda_padrao',
        'unidade_compra_padrao',
        'unidade_fiscal_padrao',
        'usa_conversao_dimensional',
        'controla_composicao_fisica',
        'tipo_composicao_fisica',
        'exige_certificado_qualidade',
    }
)

# Nenhum campo da família é sensível: pesos e observações ficam fora por serem
# ruído dimensional (mesma política do produto), não por sigilo.
FAMILIA_CAMPOS_MASCARADOS: frozenset[str] = frozenset()

FAMILIA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        # Derivadas de tipo_regra_codigo no save(): registrar as duas coisas seria diff duplicado.
        'usa_rosca_conexao',
        'usa_schedule',
        'usa_polegada_principal',
        'usa_polegada_secundaria',
        'peso_por_metro_kg',
        'peso_por_peca_kg',
        'peso_por_chapa_kg',
        'densidade',
        'comprimento_padrao_barra_m',
        'unidades_venda_permitidas',
        'unidades_compra_permitidas',
        'observacoes_conversao',
        'ncm_padrao',
        'material_base_ref',
    }
)

FAMILIA_ALLOWLIST: frozenset[str] = FAMILIA_CAMPOS_VALOR | FAMILIA_CAMPOS_MASCARADOS

# ---------------------------------------------------------------------------
# Documentos (Sprint 3.18 — rail do chatter nas telas de documento)
#
# Critério igual para todos os seis, para a allowlist ser auditável:
#   1. SOMENTE o cabeçalho do documento. Itens são outros modelos (ItemProposta,
#      ItemPedidoCompra, ItemNFeSaida...), sem chave em MODELOS_AUDITADOS.
#   2. FK entra na forma `campo_id` (inteiro). `capturar_snapshot` resolve `x_id`
#      antes de tentar o objeto; sem isso o diff gravaria o `__str__` da instância.
#   3. Excluídos: `id`; `criado_em`/`atualizado_em` (auto_now — muda em toda save());
#      JSON/Array (payload bruto ou derivado); `xml_*` (blob, e o bloqueio semântico
#      já pegaria o substring 'xml'); campos `*_por`/`numero_reservado_por` (FK de
#      usuário, já registrados como `ator` do próprio RegistroAuditoria); e os
#      carimbos de efeito (`efeitos_*`), que o sistema escreve, não o usuário.
#   4. Mascarados: texto livre digitado pelo usuário (observações, mensagens,
#      motivos) — mesma política de `observacoes` em cliente/fornecedor.
# ---------------------------------------------------------------------------

COTACAO_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'numero',
        'data',
        'prazo_resposta',
        'status',
        'proposta_id',
        'responsavel_id',
    }
)

COTACAO_CAMPOS_MASCARADOS: frozenset[str] = frozenset({'observacao'})

COTACAO_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        'criado_em',
        'atualizado_em',
        # Forma objeto das FKs auditadas em _id.
        'proposta',
        'responsavel',
    }
)

COTACAO_ALLOWLIST: frozenset[str] = COTACAO_CAMPOS_VALOR | COTACAO_CAMPOS_MASCARADOS

PROPOSTA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'numero',
        'data',
        'validade',
        'validade_dias',
        'status',
        'operacao_fiscal',
        'usar_cenario_fiscal_saida',
        'cenario_fiscal_saida_id',
        'condicao_pagamento_texto',
        'quantidade_parcelas',
        'valor_total',
        'valor_frete',
        'frete_texto',
        'prazo_entrega_texto',
        'cliente_id',
        'cliente_avulso_nome',
        'empresa_emitente_id',
        'uf_origem',
        'uf_destino_avulso',
        'vendedor',
        'vendedor_ref_id',
        'homologacao_fiscal_status',
    }
)

PROPOSTA_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {
        'mensagem_comercial',
        'observacoes_proposta',
        'referencia_cliente',
        'homologacao_fiscal_observacao',
        'motivo_recuperacao',
    }
)

PROPOSTA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        # Derivadas de condicao_pagamento_texto no validate(); duplicariam o diff.
        'dias_parcelas',
        'vencimentos_previstos',
        'homologacao_fiscal_resumo',
        'homologacao_fiscal_em',
        # Carimbos da recuperação: o evento já tem PropostaComercialHistorico próprio.
        'recuperada_em',
        'recuperada_por',
        'recuperada_por_id',
        'status_anterior_recuperacao',
        'cliente',
        'empresa_emitente',
        'vendedor_ref',
        'cenario_fiscal_saida',
    }
)

PROPOSTA_ALLOWLIST: frozenset[str] = PROPOSTA_CAMPOS_VALOR | PROPOSTA_CAMPOS_MASCARADOS

PEDIDO_VENDA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'numero',
        'data',
        'status',
        'condicao_pagamento_texto',
        'quantidade_parcelas',
        'valor_total',
        'valor_frete',
        'desconto_cabecalho_tipo',
        'desconto_cabecalho',
        'vendedor',
        'vendedor_ref_id',
        'prazo_entrega',
        'prazo_entrega_texto',
        'cliente_id',
        'empresa_emitente_id',
        'proposta_id',
    }
)

PEDIDO_VENDA_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {'observacoes_comerciais', 'observacoes_internas'}
)

PEDIDO_VENDA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        'dias_parcelas',
        'vencimentos_previstos',
        # Snapshot do wizard de conversão (JSON): reescrito por fluxo, não pelo usuário.
        'snapshot_conversao',
        'cliente',
        'empresa_emitente',
        'vendedor_ref',
        'proposta',
    }
)

PEDIDO_VENDA_ALLOWLIST: frozenset[str] = (
    PEDIDO_VENDA_CAMPOS_VALOR | PEDIDO_VENDA_CAMPOS_MASCARADOS
)

PEDIDO_COMPRA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'numero',
        'data',
        'status',
        'condicao_pagamento_texto',
        'quantidade_parcelas',
        'valor_total',
        'prazo_entrega_texto',
        'data_prevista_entrega',
        'desconto_cabecalho_tipo',
        'desconto_cabecalho',
        'fornecedor_id',
    }
)

PEDIDO_COMPRA_CAMPOS_MASCARADOS: frozenset[str] = frozenset({'observacoes'})

PEDIDO_COMPRA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {'id', 'dias_parcelas', 'vencimentos_previstos', 'fornecedor'}
)

PEDIDO_COMPRA_ALLOWLIST: frozenset[str] = (
    PEDIDO_COMPRA_CAMPOS_VALOR | PEDIDO_COMPRA_CAMPOS_MASCARADOS
)

NFE_SAIDA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'numero',
        'data',
        'valor_total',
        'status',
        'status_conferencia',
        'status_emissao_sefaz',
        'fin_nfe',
        'modo_atendimento_estoque',
        'condicao_pagamento_texto',
        'quantidade_parcelas',
        'valor_frete',
        'modalidade_frete',
        'quantidade_volumes',
        'peso_bruto',
        'peso_liquido',
        'especie_volumes',
        'marca_volumes',
        'numeracao_volumes',
        'placa_veiculo',
        'uf_veiculo',
        'ind_final',
        'ind_pres',
        'ambiente_emissao',
        'serie_nfe',
        'numero_nfe',
        'chave_acesso',
        'tipo_emissao',
        'pedido_cliente_numero',
        'indicadores_fiscais_confirmados',
        'conferencia_validada_em',
        'conferencia_marcada_pronta_em',
        'cstat_autorizacao',
        'protocolo_autorizacao',
        'autorizada_em',
        'cancelada_em',
        'cliente_id',
        'fornecedor_id',
        'transportadora_id',
        'empresa_emitente_id',
        'pedido_venda_id',
        'faturamento_pedido_venda_id',
        'chave_nfe_referenciada',
    }
)

NFE_SAIDA_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {
        'observacoes_nfe',
        'informacoes_adicionais',
        'observacoes_internas',
        'informacoes_fisco',
        'pedido_cliente_observacao',
        'observacao_origem',
        'motivo_cancelamento',
        'motivo_autorizacao',
        'xmotivo_lote',
        'conferencia_ultima_mensagem',
    }
)

NFE_SAIDA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        'dias_parcelas',
        'vencimentos_finais',
        'titulos_receber',
        'codigo_numerico',
        'digito_verificador',
        'recibo_lote',
        'cstat_lote',
        'chave_acesso_preliminar',
        'serie_fiscal_preliminar',
        'numero_fiscal_preliminar',
        'xml_preliminar_gerado_em',
        'numero_reservado_em',
        'numero_reservado_por',
        'numero_reservado_por_id',
        'conferencia_validada_por',
        'conferencia_validada_por_id',
        'conferencia_marcada_pronta_por',
        'conferencia_marcada_pronta_por_id',
        'cancelada_por',
        'cancelada_por_id',
        'efeitos_autorizacao_aplicados_em',
        'efeitos_cancelamento_aplicados_em',
        'efeitos_cancelamento_por',
        'efeitos_cancelamento_por_id',
        'nfe_entrada_conferencia_origem',
        'cliente',
        'fornecedor',
        'transportadora',
        'empresa_emitente',
        'pedido_venda',
        'faturamento_pedido_venda',
    }
    # Blob de XML: listados por prefixo porque o nome é muitos e o bloqueio semântico
    # já os impediria de gravar valor; manter explícito evita surpresa ao ler a policy.
    | frozenset(
        {
            'xml_preliminar',
            'xml_assinado',
            'xml_envio',
            'xml_retorno',
            'xml_autorizado',
            'xml_retorno_lote',
            'xml_protocolo',
            'xml_nfe_gerado',
            'xml_envio_lote',
        }
    )
)

NFE_SAIDA_ALLOWLIST: frozenset[str] = NFE_SAIDA_CAMPOS_VALOR | NFE_SAIDA_CAMPOS_MASCARADOS

NFE_ENTRADA_CAMPOS_VALOR: frozenset[str] = frozenset(
    {
        'numero',
        'serie',
        'chave_acesso',
        'data',
        'valor_total',
        'tipo_origem',
        'status_operacional',
        'status_emissao_sefaz',
        'ambiente_emissao',
        'fin_nfe',
        'nat_op',
        'serie_nfe',
        'numero_nfe',
        'chave_nfe_referenciada',
        'cstat_autorizacao',
        'protocolo_autorizacao',
        'autorizada_em',
        'importado_em',
        'fornecedor_id',
        'empresa_emitente_id',
        'cliente_destinatario_id',
        'pedido_compra_id',
        'cte_id',
        'nfe_saida_origem_id',
        'nfe_saida_historica_origem_id',
    }
)

NFE_ENTRADA_CAMPOS_MASCARADOS: frozenset[str] = frozenset(
    {'motivo_autorizacao', 'xmotivo_lote'}
)

NFE_ENTRADA_CAMPOS_EXCLUIDOS: frozenset[str] = frozenset(
    {
        'id',
        # Corpo do documento importado: JSON por linha, reescrito em lote na importação.
        'emit_json',
        'dest_json',
        'itens_json',
        # Contém o substring 'arquivo' do bloqueio semântico; inofensivo, mas ruído.
        'nome_arquivo',
        'codigo_numerico',
        'digito_verificador',
        'recibo_lote',
        'cstat_lote',
        'numero_reservado_em',
        'numero_reservado_por',
        'numero_reservado_por_id',
        'efeitos_devolucao_aplicados_em',
        'efeitos_devolucao_por',
        'efeitos_devolucao_por_id',
        'fornecedor',
        'empresa_emitente',
        'cliente_destinatario',
        'pedido_compra',
        'cte',
        'nfe_saida_origem',
        'nfe_saida_historica_origem',
    }
    | frozenset(
        {
            'xml_importado',
            'xml_nfe_gerado',
            'xml_assinado',
            'xml_envio',
            'xml_retorno',
            'xml_autorizado',
            'xml_retorno_lote',
            'xml_protocolo',
            'xml_envio_lote',
        }
    )
)

NFE_ENTRADA_ALLOWLIST: frozenset[str] = (
    NFE_ENTRADA_CAMPOS_VALOR | NFE_ENTRADA_CAMPOS_MASCARADOS
)

# Bloqueio semântico obrigatório (nunca armazenar valor).
CAMPOS_BLOQUEADOS_SEMPRE: frozenset[str] = frozenset(
    {
        'password',
        'senha',
        'token',
        'secret',
        'certificado',
        'chave_privada',
        'private_key',
        'xml',
        'pdf',
        'arquivo',
        'credencial',
        'credential',
    }
)

STRING_MAX_LEN = 500
