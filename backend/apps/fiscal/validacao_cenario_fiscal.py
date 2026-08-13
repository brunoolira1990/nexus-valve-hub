"""Validação de itens da NF-e Saída contra o Cenário Fiscal vigente.

Compara o snapshot fiscal atual de cada item com a regra de saída que o
cenário fiscal homologado aplica hoje (produto/NCM + rota UF + finalidade).

Gera:
- Pendência: item sem regra no cenário (NCM/rota não cobertos) — emissão
  bloqueada até a cobertura ser criada ou o item corrigido.
- Alerta: snapshot divergente da regra vigente (CFOP/CST/alíquota mudaram
  desde a última atualização de impostos) — recomenda "Atualizar impostos".
- Info: regra vigente aplicada com identificação do cenário (fonte
  CENARIO_SAIDA), para auditoria da conferência.
"""
from __future__ import annotations

from typing import Any

from apps.fiscal.nfe_destinatario_fiscal import resolver_perfil_destinatario_nf


def _only_digits_cfop(value: str | None) -> str:
    return ''.join(c for c in (value or '') if c.isdigit())


def _norm_uf(value: str | None) -> str:
    return (value or '').strip().upper()[:2]


def _texto(valor: Any) -> str:
    return (valor or '').strip() if isinstance(valor, (str, bytes)) else ''


def validar_itens_contra_cenario_fiscal(
    nf: Any,
    itens: list,
    *,
    uf_origem: str,
    uf_destino: str,
    alertas_hook=None,
) -> dict[str, list[dict[str, Any]]]:
    """Valida cada item da NF-e contra a regra vigente do cenário fiscal.

    `alertas_hook(grupos, tipo, codigo, grupo, mensagem, item_id)` opcional
    registra alertas na validação principal da NF-e.

    Retorna `por_item`: lista com um registro por item contendo
    origem, regra vigente, divergências e mensagens.
    """
    from apps.regras_fiscais.saida_fiscal import (
        buscar_regra_fiscal_nfe_saida_rascunho,
    )

    por_item: list[dict[str, Any]] = []
    perfil_nf = resolver_perfil_destinatario_nf(nf)
    regras_sem_cobertura: list[str] = []

    for item in itens:
        from apps.fiscal.snapshot_fiscal_helpers import get_ncm_snapshot

        ncm_item = (get_ncm_snapshot(item.snapshot_fiscal) or '').strip()
        if not ncm_item and getattr(item, 'produto', None) is not None:
            ncm_item = (
                getattr(item.produto, 'get_ncm_efetivo_codigo', lambda: None)()
                or getattr(item.produto, 'ncm', None)
                or ''
            ).strip()
        if not ncm_item:
            ncm_item = ((item.snapshot_produto or {}).get('ncm') or '').strip()

        produto = getattr(item, 'produto', None)
        entrada = {
            'item_id': item.pk,
            'descricao': (
                (item.snapshot_produto or {}).get('descricao')
                if item.snapshot_produto else None
            ) or (produto.descricao if produto is not None else '')
            or f'Item #{item.pk}',
            'ncm': ncm_item,
            'origem': 'NAO_ENCONTRADA',
            'regra_id': None,
            'regra_nome': '',
            'cenario_id': None,
            'cenario_nome': '',
            'cfop_atual': '',
            'cfop_vigente': '',
            'cst_atual': '',
            'cst_vigente': '',
            'divergente': False,
            'mensagens': [],
        }

        snapshot = item.snapshot_fiscal or {}
        entrada['cfop_atual'] = _only_digits_cfop(snapshot.get('cfop') or snapshot.get('cfop_venda') or '')
        entrada['cst_atual'] = _texto(
            snapshot.get('cst_icms')
            or snapshot.get('csosn')
            or snapshot.get('cst_icms_st'),
        )
        entrada['regra_nome'] = _texto(snapshot.get('regra_fiscal_saida_nome'))
        entrada['cenario_id'] = snapshot.get('cenario_fiscal_saida_id')
        entrada['cenario_nome'] = _texto(snapshot.get('cenario_fiscal_saida_nome'))

        if not ncm_item or len(_only_digits_cfop(ncm_item)) < 8:
            entrada['mensagens'].append('NCM incompleto: regra do cenário não pode ser verificada.')
            if alertas_hook is not None:
                alertas_hook(
                    'fiscal',
                    'ITENS_CENARIO_SEM_NCM',
                    'Item sem NCM válido para verificação do cenário fiscal.',
                    item.pk,
                )
            por_item.append(entrada)
            continue

        busca, regra, _filtros = buscar_regra_fiscal_nfe_saida_rascunho(
            produto_id=item.produto_id,
            ncm=ncm_item.strip(),
            uf_origem=uf_origem,
            uf_destino=uf_destino,
            cenario_id=snapshot.get('cenario_fiscal_saida_id'),
            produto=produto,
            destinatario_contribuinte=perfil_nf.destinatario_contribuinte,
            consumidor_final=perfil_nf.consumidor_final,
            tipo_operacao='VENDA',
        )

        entrada['origem'] = busca.get('origem', 'NAO_ENCONTRADA')
        if regra is not None:
            entrada['regra_id'] = regra.pk
            entrada['regra_nome'] = _texto(regra.nome) or _texto(regra.descricao_cenario) or f'Regra #{regra.pk}'
            if regra.cenario_id:
                entrada['cenario_id'] = regra.cenario_id
                entrada['cenario_nome'] = _texto(regra.cenario.nome) if regra.cenario else ''
            entrada['cfop_vigente'] = _only_digits_cfop(regra.cfop_venda)
            entrada['cst_vigente'] = _texto(regra.cst_icms or regra.csosn)

            divergencias: list[str] = []
            if entrada['cfop_atual'] and entrada['cfop_vigente'] and entrada['cfop_atual'] != entrada['cfop_vigente']:
                divergencias.append(f"CFOP {entrada['cfop_atual']} difere do vigente {entrada['cfop_vigente']}")
            if entrada['cst_atual'] and entrada['cst_vigente'] and entrada['cst_atual'] != entrada['cst_vigente']:
                divergencias.append(f"CST {entrada['cst_atual']} difere do vigente {entrada['cst_vigente']}")

            if divergencias:
                entrada['divergente'] = True
                if alertas_hook is not None:
                    alertas_hook(
                        'fiscal',
                        'ITENS_CENARIO_SNAPSHOT_DESATUALIZADO',
                        f'{divergencias[0]}. Execute "Atualizar impostos" para alinhar a NF-e ao cenário fiscal vigente.',
                        item.pk,
                    )
            else:
                entrada['mensagens'].append(
                    f'Regra do cenário aplicada: {entrada["regra_nome"]} (CFOP {entrada["cfop_vigente"] or "—"}).',
                )
        else:
            # Regra não encontrada no cenário homologado: pendência bloqueante.
            if alertas_hook is not None:
                alertas_hook(
                    'fiscal',
                    'ITENS_CENARIO_SEM_COBERTURA',
                    f'Item {item.pk}: nenhuma regra do cenário fiscal cobre NCM {ncm_item.strip()} '
                    f'na rota {uf_origem}→{uf_destino}.',
                    item.pk,
                )
            regras_sem_cobertura.append(f'Item {item.pk} — {entrada["descricao"]}')

        por_item.append(entrada)

    return {
        'por_item': por_item,
        'itens_sem_cobertura': regras_sem_cobertura,
        'com_divergencia': [e for e in por_item if e.get('divergente')],
        'cenario_verificado': any(e.get('cenario_id') for e in por_item),
    }
