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
