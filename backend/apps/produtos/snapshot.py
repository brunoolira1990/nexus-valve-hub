from __future__ import annotations


def build_produto_snapshot(produto):
    ncm = produto.get_ncm_efetivo()
    principal = getattr(produto, 'polegada_principal_ref', None)
    secundaria = getattr(produto, 'polegada_secundaria_ref', None)
    return {
        'produto_id': produto.id,
        'codigo_completo_snapshot': produto.codigo_completo,
        'descricao_produto_snapshot': produto.descricao,
        'ncm_codigo_snapshot': getattr(ncm, 'codigo', '') if ncm else '',
        'ncm_descricao_snapshot': getattr(ncm, 'descricao', '') if ncm else '',
        'unidade_snapshot': produto.get_unidade_estoque_efetiva(),
        'controla_composicao_fisica_efetivo': produto.get_controla_composicao_fisica_efetivo(),
        'tipo_composicao_fisica_efetivo': produto.get_tipo_composicao_fisica_efetivo(),
        'unidade_base_composicao_fisica': produto.get_unidade_base_composicao_fisica(),
        'familia_snapshot': produto.familia.codigo_figura if produto.familia_id else '',
        'material_snapshot': produto.material or '',
        'norma_snapshot': produto.norma or '',
        'polegada_principal_snapshot': principal.descricao if principal else '',
        'polegada_secundaria_snapshot': secundaria.descricao if secundaria else '',
        'codigo_polegada_principal_snapshot': (principal.codigo_oficial if principal else ''),
        'codigo_polegada_secundaria_snapshot': (secundaria.codigo_oficial if secundaria else ''),
    }
