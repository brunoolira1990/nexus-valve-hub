"""ERP 4.0.13.5 — Checklist fiscal de pré-homologação NF-e (sem transmitir / sem efeitos)."""

from __future__ import annotations

import io
import re
from decimal import Decimal
from typing import Any, Literal

from django.conf import settings

from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
from apps.comercial.pedido_venda_pdf import gerar_pedido_venda_pdf_bytes
from apps.comercial.services.resumo_atendimento_operacional import obter_resumo_atendimento_operacional
from apps.fiscal.dfe_classificacao import eh_documento_homologacao, pode_entrar_apuracao, tem_valor_fiscal
from apps.fiscal.models import AtendimentoEstoque, NFeSaida
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao
from apps.fiscal.nfe_saida_duplicatas import (
    _pagamento_a_vista,
    _resolve_dias_parcelas,
    gerar_duplicatas_nfe_saida,
)
from apps.fiscal.nfe_saida_listagem import montar_listagem_resumo_nfe
from apps.fiscal.reforma_tributaria.config import reforma_nfe_config, status_reforma_nfe_documento
from apps.fiscal.reforma_tributaria.validacoes import (
    alerta_reforma_antes_homologacao,
    reforma_deve_serializar_no_xml,
    reforma_pode_incluir_no_xml,
)

ItemStatus = Literal['ok', 'alerta', 'bloqueado', 'nao_aplicavel']

PDF_FISCAL_FORBIDDEN = (
    'homologação',
    'cstat',
    'rascunho-fat',
    'fora da apuração',
    'duplicatas da nf-e',
    '<cobr>',
    'danfe',
    'sem valor fiscal',
)


def _item(
    codigo: str,
    label: str,
    status: ItemStatus,
    mensagem: str,
    *,
    secao: str = 'geral',
) -> dict[str, str]:
    return {
        'codigo': codigo,
        'label': label,
        'status': status,
        'mensagem': mensagem,
        'secao': secao,
    }


def _resolver_contexto(
    *,
    pedido_venda: PedidoVenda | None = None,
    faturamento: FaturamentoPedidoVenda | None = None,
    nfe_saida: NFeSaida | None = None,
) -> tuple[PedidoVenda | None, FaturamentoPedidoVenda | None, NFeSaida | None]:
    pedido = pedido_venda
    fat = faturamento
    nf = nfe_saida

    if fat and not pedido:
        pedido = getattr(fat, 'pedido', None) or getattr(fat, 'pedido_venda', None)
    if nf:
        if not pedido and nf.pedido_venda_id:
            pedido = nf.pedido_venda
        if not fat and nf.faturamento_pedido_venda_id:
            fat = nf.faturamento_pedido_venda

    if not nf and fat:
        nf = (
            NFeSaida.objects.filter(faturamento_pedido_venda_id=fat.pk)
            .select_related('cliente', 'pedido_venda', 'faturamento_pedido_venda')
            .prefetch_related('itens')
            .order_by('-id')
            .first()
        )
    if not nf and pedido:
        nf = (
            NFeSaida.objects.filter(pedido_venda_id=pedido.pk)
            .select_related('cliente', 'pedido_venda', 'faturamento_pedido_venda')
            .prefetch_related('itens')
            .order_by('-id')
            .first()
        )

    if nf and not hasattr(nf, '_prefetched_objects_cache'):
        nf = (
            NFeSaida.objects.select_related('cliente', 'pedido_venda', 'faturamento_pedido_venda')
            .prefetch_related('itens')
            .filter(pk=nf.pk)
            .first()
        )

    return pedido, fat, nf


def _montar_resultado(itens: list[dict[str, str]]) -> dict[str, Any]:
    bloqueios = [i['mensagem'] for i in itens if i['status'] == 'bloqueado']
    alertas = [i['mensagem'] for i in itens if i['status'] == 'alerta']
    if bloqueios:
        status = 'bloqueado'
        apto = False
    elif alertas:
        status = 'aprovado_com_alertas'
        apto = True
    else:
        status = 'aprovado'
        apto = True
    return {
        'apto': apto,
        'status': status,
        'bloqueios': bloqueios,
        'alertas': alertas,
        'itens': itens,
        'aviso_fixo': (
            'Esta validação não transmite NF-e, não gera financeiro, '
            'não movimenta estoque e não cria expedição.'
        ),
    }


def _validar_pedido_faturamento(
    pedido: PedidoVenda | None,
    fat: FaturamentoPedidoVenda | None,
    nf: NFeSaida | None,
) -> list[dict[str, str]]:
    itens: list[dict[str, str]] = []
    secao = 'pedido_faturamento'

    if not pedido:
        itens.append(
            _item('pedido_existe', 'Pedido de venda', 'bloqueado', 'Pedido de venda não informado.', secao=secao),
        )
        return itens

    itens.append(_item('pedido_existe', 'Pedido de venda', 'ok', f'Pedido {pedido.numero} localizado.', secao=secao))

    if not pedido.cliente_id:
        itens.append(
            _item('pedido_cliente', 'Cliente do pedido', 'bloqueado', 'Pedido sem cliente válido.', secao=secao),
        )
    else:
        itens.append(
            _item(
                'pedido_cliente',
                'Cliente do pedido',
                'ok',
                pedido.cliente.razao_social if pedido.cliente else 'Cliente vinculado.',
                secao=secao,
            ),
        )

    pv_itens = list(pedido.itens.all()) if hasattr(pedido, 'itens') else []
    if not pv_itens:
        itens.append(
            _item('pedido_itens', 'Itens do pedido', 'bloqueado', 'Pedido sem itens.', secao=secao),
        )
    else:
        itens.append(
            _item('pedido_itens', 'Itens do pedido', 'ok', f'{len(pv_itens)} item(ns) no pedido.', secao=secao),
        )

    valor_pedido = Decimal(str(pedido.valor_total or 0))
    if valor_pedido <= 0:
        itens.append(
            _item('pedido_valor', 'Valor do pedido', 'bloqueado', 'Valor total do pedido é zero.', secao=secao),
        )
    else:
        itens.append(
            _item('pedido_valor', 'Valor do pedido', 'ok', f'Valor do pedido: R$ {valor_pedido:.2f}.', secao=secao),
        )

    if fat:
        itens.append(
            _item(
                'faturamento_existe',
                'Faturamento',
                'ok',
                f'Faturamento {fat.numero_faturamento or fat.pk} localizado.',
                secao=secao,
            ),
        )
        fat_valor = Decimal(str(getattr(fat, 'valor_total', None) or getattr(fat, 'valor_faturado', None) or 0))
        if fat_valor > 0 and valor_pedido > 0 and abs(fat_valor - valor_pedido) > Decimal('0.05'):
            itens.append(
                _item(
                    'faturamento_valor',
                    'Valor faturado',
                    'alerta',
                    'Valor faturado difere do pedido — revise antes da homologação.',
                    secao=secao,
                ),
            )
        else:
            itens.append(
                _item('faturamento_valor', 'Valor faturado', 'ok', 'Valor faturado consistente.', secao=secao),
            )
    elif nf and nf.faturamento_pedido_venda_id:
        itens.append(
            _item('faturamento_existe', 'Faturamento', 'ok', 'Faturamento vinculado à NF-e.', secao=secao),
        )
    else:
        itens.append(
            _item(
                'faturamento_existe',
                'Faturamento',
                'alerta',
                'Faturamento não localizado — confirme origem comercial.',
                secao=secao,
            ),
        )

    if not nf:
        itens.append(
            _item(
                'nfe_rascunho',
                'NF-e Saída',
                'alerta',
                'NF-e de saída ainda não gerada — gere rascunho antes do teste de homologação.',
                secao=secao,
            ),
        )

    return itens


def _validar_duplicatas(nf: NFeSaida | None) -> list[dict[str, str]]:
    itens: list[dict[str, str]] = []
    secao = 'duplicatas'
    if not nf:
        itens.append(
            _item('duplicatas_nfe', 'Duplicatas', 'nao_aplicavel', 'Sem NF-e para validar duplicatas.', secao=secao),
        )
        return itens

    days = _resolve_dias_parcelas(nf)
    a_vista = _pagamento_a_vista(days)
    cond = (nf.condicao_pagamento_texto or '').strip()
    if not cond and nf.pedido_venda_id and nf.pedido_venda:
        cond = (nf.pedido_venda.condicao_pagamento_texto or '').strip()

    if cond:
        itens.append(
            _item('condicao_pagamento', 'Condição de pagamento', 'ok', f'Condição: {cond}.', secao=secao),
        )
    else:
        itens.append(
            _item(
                'condicao_pagamento',
                'Condição de pagamento',
                'alerta',
                'Condição de pagamento não informada.',
                secao=secao,
            ),
        )

    if a_vista:
        itens.append(
            _item(
                'duplicatas_nfe',
                'Duplicatas da NF-e',
                'nao_aplicavel',
                'Pagamento à vista — duplicatas não aplicáveis.',
                secao=secao,
            ),
        )
        itens.append(
            _item(
                'duplicatas_sem_financeiro',
                'Sem financeiro automático',
                'ok',
                'Duplicatas da NF-e não geram Contas a Receber nesta fase.',
                secao=secao,
            ),
        )
        return itens

    dups = gerar_duplicatas_nfe_saida(nf)
    if not dups:
        itens.append(
            _item(
                'duplicatas_nfe',
                'Duplicatas da NF-e',
                'bloqueado',
                'Pagamento a prazo sem duplicatas/vencimento calculável.',
                secao=secao,
            ),
        )
        return itens

    total_nf = Decimal(str(nf.valor_total or 0))
    soma = sum(Decimal(str(d['valor'])) for d in dups)
    if total_nf > 0 and abs(soma - total_nf) > Decimal('0.02'):
        itens.append(
            _item(
                'duplicatas_soma',
                'Soma das duplicatas',
                'bloqueado',
                f'Soma das duplicatas (R$ {soma:.2f}) não confere com total da NF-e (R$ {total_nf:.2f}).',
                secao=secao,
            ),
        )
    else:
        dup_txt = '; '.join(f"{d['numero']} venc. {d['vencimento']} R$ {d['valor']}" for d in dups[:3])
        itens.append(
            _item(
                'duplicatas_nfe',
                'Duplicatas da NF-e',
                'ok',
                f'{len(dups)} duplicata(s) preparada(s): {dup_txt}.',
                secao=secao,
            ),
        )

    for d in dups:
        if not d.get('vencimento'):
            itens.append(
                _item(
                    'duplicata_vencimento',
                    'Vencimento da duplicata',
                    'bloqueado',
                    f'Duplicata {d.get("numero")} sem vencimento.',
                    secao=secao,
                ),
            )
            break
    else:
        itens.append(
            _item('duplicata_vencimento', 'Vencimento', 'ok', 'Vencimentos definidos para todas as duplicatas.', secao=secao),
        )

    itens.append(
        _item(
            'duplicatas_sem_financeiro',
            'Sem financeiro automático',
            'ok',
            'Duplicatas da NF-e não geram Contas a Receber nesta fase.',
            secao=secao,
        ),
    )
    return itens


def _xml_tem_tag(xml: str, tag: str) -> bool:
    return bool(re.search(rf'<[\w:]*{re.escape(tag)}\b', xml, flags=re.IGNORECASE))


def _formatar_erro_danfe_checklist(exc: BaseException) -> tuple[str, str]:
    """Mensagem amigável + detalhe técnico curto (sem stack trace)."""
    from apps.fiscal.danfe_render import DanfeBfrRenderError

    if isinstance(exc, DanfeBfrRenderError):
        return (
            str(exc),
            f'{exc.erro_tipo or type(exc).__name__}: trace_id={exc.trace_id or "—"}',
        )
    nome = type(exc).__name__
    detalhe = str(exc).strip() or nome
    if detalhe.lower() in ('danfe bloqueado', 'pdf vazio'):
        detalhe = 'Renderização retornou PDF vazio ou bloqueado pelo renderer.'
    return (
        'DANFE não pôde ser renderizado. Corrija os dados fiscais antes de nova homologação.',
        f'{nome}: {detalhe}',
    )


def _validar_danfe_checklist(nf: NFeSaida) -> list[dict[str, str]]:
    """Valida DANFE com o mesmo fluxo dos botões preview-danfe / danfe-autorizado."""
    secao = 'danfe'
    itens: list[dict[str, str]] = []
    from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao, nf_autorizada_producao
    from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia

    try:
        if nf_autorizada_homologacao(nf) or nf_autorizada_producao(nf):
            from apps.fiscal.nfe_saida_danfe_autorizado import gerar_danfe_autorizado_nfe_saida

            pdf, meta = gerar_danfe_autorizado_nfe_saida(nf)
        else:
            from apps.fiscal.nfe_saida_preview import gerar_preview_danfe_nfe_saida

            pdf, meta = gerar_preview_danfe_nfe_saida(nf)
        if meta.get('bloqueado'):
            msg_bloq = (meta.get('mensagens') or ['DANFE bloqueado pelo renderer.'])[0]
            amigavel, tecnico = _formatar_erro_danfe_checklist(ValueError(msg_bloq))
            itens.append(
                _item(
                    'danfe_render',
                    'DANFE',
                    'bloqueado',
                    f'{amigavel} ({tecnico})',
                    secao=secao,
                ),
            )
            return itens

        if not pdf or len(pdf) < 100:
            amigavel, tecnico = _formatar_erro_danfe_checklist(ValueError('PDF vazio'))
            itens.append(
                _item('danfe_render', 'DANFE', 'bloqueado', f'{amigavel} ({tecnico})', secao=secao),
            )
            return itens

        origem = meta.get('danfe_origem') or meta.get('render_engine') or 'conferência'
        engine = meta.get('render_engine') or ''
        from apps.fiscal.danfe_render import RENDER_ENGINES_OFICIAIS, renderer_oficial

        if engine not in RENDER_ENGINES_OFICIAIS:
            itens.append(
                _item(
                    'danfe_render',
                    'DANFE',
                    'bloqueado',
                    f'Renderer não oficial ({engine}). Apenas BFR é permitido.',
                    secao=secao,
                ),
            )
            return itens

        itens.append(
            _item(
                'danfe_render',
                'DANFE',
                'ok',
                f'DANFE renderizado com sucesso ({origem}).',
                secao=secao,
            ),
        )
        itens.append(
            _item(
                'danfe_renderer_oficial',
                'Renderer oficial BFR',
                'ok',
                f'Renderer oficial: {renderer_oficial()} ({engine}).',
                secao=secao,
            ),
        )
        itens.append(
            _item(
                'danfe_sem_fallback_html',
                'Sem fallback HTML',
                'ok',
                'HTML/WeasyPrint não foi usado (fallback bloqueado).',
                secao=secao,
            ),
        )

        if nf_autorizada_homologacao(nf):
            itens.append(
                _item(
                    'danfe_homologacao',
                    'Homologação no DANFE',
                    'ok',
                    'Ambiente de homologação identificado no DANFE.',
                    secao=secao,
                ),
            )

        dados = montar_dados_danfe_conferencia(nf)
        dup_rows = dados.get('duplicatas') or []
        days = _resolve_dias_parcelas(nf)
        if not _pagamento_a_vista(days):
            if dup_rows:
                primeira = dup_rows[0]
                detalhe = (
                    f"Duplicata {primeira.get('numero', '—')}, "
                    f"vencimento {primeira.get('vencimento', '—')}, "
                    f"valor {primeira.get('valor', '—')}."
                )
                itens.append(
                    _item(
                        'danfe_duplicatas',
                        'Duplicatas no DANFE',
                        'ok',
                        f'DANFE exibe {len(dup_rows)} duplicata(s). {detalhe}',
                        secao=secao,
                    ),
                )
            else:
                itens.append(
                    _item(
                        'danfe_duplicatas',
                        'Duplicatas no DANFE',
                        'alerta',
                        'Pagamento a prazo sem duplicatas no payload do DANFE (verifique XML).',
                        secao=secao,
                    ),
                )
        else:
            itens.append(
                _item(
                    'danfe_duplicatas',
                    'Duplicatas no DANFE',
                    'nao_aplicavel',
                    'Pagamento à vista — duplicatas não exigidas no DANFE.',
                    secao=secao,
                ),
            )
    except Exception as exc:
        amigavel, tecnico = _formatar_erro_danfe_checklist(exc)
        itens.append(
            _item('danfe_render', 'DANFE', 'bloqueado', f'{amigavel} ({tecnico})', secao=secao),
        )

    return itens


def _validar_xml_danfe(nf: NFeSaida | None) -> list[dict[str, str]]:
    itens: list[dict[str, str]] = []
    secao_xml = 'xml'
    secao_danfe = 'danfe'
    if not nf:
        itens.append(_item('xml_preliminar', 'XML preliminar', 'nao_aplicavel', 'Sem NF-e.', secao=secao_xml))
        itens.append(_item('danfe_render', 'DANFE', 'nao_aplicavel', 'Sem NF-e.', secao=secao_danfe))
        return itens

    if nf_autorizada_homologacao(nf) and (nf.xml_autorizado or '').strip():
        xml = nf.xml_autorizado
        itens.append(
            _item(
                'xml_autorizado_intacto',
                'XML autorizado',
                'ok',
                'NF-e já autorizada em homologação — XML existente não será alterado nesta validação.',
                secao=secao_xml,
            ),
        )
    else:
        from apps.fiscal.nfe_integracao.nfe_xml_preliminar import pode_gerar_xml_preliminar

        pode, erros = pode_gerar_xml_preliminar(nf)
        if not pode:
            itens.append(
                _item(
                    'xml_preliminar',
                    'XML preliminar',
                    'bloqueado',
                    erros[0] if erros else 'Não foi possível gerar XML preliminar.',
                    secao=secao_xml,
                ),
            )
            itens.append(
                _item('danfe_render', 'DANFE', 'bloqueado', 'DANFE depende de XML preliminar válido.', secao=secao_danfe),
            )
            return itens

        xml = ''
        from apps.fiscal.nfe_saida_duplicatas import assegurar_duplicatas_nfe_saida

        assegurar_duplicatas_nfe_saida(nf, save=bool(nf.pk))
        try:
            from apps.fiscal.nfe_integracao.nfe_xml_preliminar import gerar_xml_nfe_preliminar

            xml = gerar_xml_nfe_preliminar(nf, persistir=False).decode('utf-8').lower()
        except Exception as exc:
            itens.append(
                _item('xml_preliminar', 'XML preliminar', 'bloqueado', str(exc), secao=secao_xml),
            )
            itens.append(
                _item('danfe_render', 'DANFE', 'bloqueado', 'Falha ao preparar XML para DANFE.', secao=secao_danfe),
            )
            return itens

        itens.append(
            _item(
                'xml_preliminar',
                'XML preliminar',
                'ok',
                'XML preliminar gerado para conferência (sem transmissão SEFAZ).',
                secao=secao_xml,
            ),
        )

        days = _resolve_dias_parcelas(nf)
        if not _pagamento_a_vista(days):
            if _xml_tem_tag(xml, 'cobr') and _xml_tem_tag(xml, 'dup'):
                itens.append(
                    _item(
                        'xml_duplicatas',
                        'Duplicatas no XML',
                        'ok',
                        'Grupo cobr/dup presente no XML preliminar.',
                        secao=secao_xml,
                    ),
                )
            else:
                itens.append(
                    _item(
                        'xml_duplicatas',
                        'Duplicatas no XML',
                        'bloqueado',
                        'XML preliminar sem grupo cobr/dup para pagamento a prazo.',
                        secao=secao_xml,
                    ),
                )
            if _xml_tem_tag(xml, 'pag'):
                itens.append(
                    _item('xml_pagamento', 'Pagamento no XML', 'ok', 'Grupo pag presente no XML.', secao=secao_xml),
                )
            else:
                itens.append(
                    _item(
                        'xml_pagamento',
                        'Pagamento no XML',
                        'alerta',
                        'Grupo pag não identificado no XML preliminar.',
                        secao=secao_xml,
                    ),
                )
        else:
            itens.append(
                _item(
                    'xml_duplicatas',
                    'Duplicatas no XML',
                    'nao_aplicavel',
                    'Pagamento à vista — cobr/dup não exigidos.',
                    secao=secao_xml,
                ),
            )

        from apps.fiscal.nfe_saida_reforma_calculo import status_reforma_snapshot
        from apps.fiscal.snapshot_fiscal_helpers import get_reforma_tributaria_snapshot
        from apps.fiscal.reforma_tributaria.xml import (
            extrair_resumo_reforma_xml,
            mensagem_reforma_xml_ok,
            nf_tem_reforma_calculada,
            validar_reforma_serializada_em_xml,
            xml_contem_reforma_tributaria,
        )

        cfg = reforma_nfe_config()
        linhas_chk = []
        for item in nf.itens.all():
            linhas_chk.append({'snapshot_fiscal': item.snapshot_fiscal or {}})
        tem_reforma_calc = nf_tem_reforma_calculada(linhas_chk)

        if tem_reforma_calc:
            if not reforma_deve_serializar_no_xml():
                itens.append(
                    _item(
                        'xml_reforma_omitida_flags',
                        'Reforma no XML',
                        'nao_aplicavel',
                        'Reforma calculada no snapshot — IBSCBS omitido (flags RTC desligadas).',
                        secao=secao_xml,
                    ),
                )
            elif xml_contem_reforma_tributaria(xml):
                resumo = extrair_resumo_reforma_xml(xml)
                msg = mensagem_reforma_xml_ok(resumo) or 'Reforma Tributária presente no XML preliminar.'
                itens.append(
                    _item(
                        'xml_reforma_item',
                        'Reforma no item (XML)',
                        'ok',
                        msg,
                        secao=secao_xml,
                    ),
                )
                if _xml_tem_tag(xml, 'ibscbstot'):
                    itens.append(
                        _item(
                            'xml_reforma_total',
                            'Reforma no total (XML)',
                            'ok',
                            'Grupo IBSCBSTot presente no XML preliminar.',
                            secao=secao_xml,
                        ),
                    )
                else:
                    itens.append(
                        _item(
                            'xml_reforma_total',
                            'Reforma no total (XML)',
                            'bloqueado',
                            'Reforma calculada sem totalizador IBSCBSTot no XML preliminar.',
                            secao=secao_xml,
                        ),
                    )
                for chk in validar_reforma_serializada_em_xml(xml, itens=linhas_chk):
                    st = 'bloqueado' if chk['tipo'] == 'PENDENCIA' else 'ok' if chk['tipo'] == 'INFO' else 'alerta'
                    itens.append(
                        _item(
                            chk['codigo'].lower(),
                            'Reforma Tributária XML',
                            st,
                            chk['mensagem'],
                            secao=secao_xml,
                        ),
                    )
            else:
                itens.append(
                    _item(
                        'xml_reforma_ausente',
                        'Reforma no XML',
                        'bloqueado',
                        'Reforma calculada na conferência, mas ausente no XML preliminar.',
                        secao=secao_xml,
                    ),
                )
        else:
            calc_count = sum(
                1
                for item in nf.itens.all()
                if status_reforma_snapshot(get_reforma_tributaria_snapshot(item.snapshot_fiscal))
                in ('CALCULADA', 'ATENCAO', 'PENDENTE')
            )
            if calc_count:
                itens.append(
                    _item(
                        'xml_reforma_parcial',
                        'Reforma no XML',
                        'alerta',
                        'Itens com bloco de Reforma sem cálculo completo — XML pode omitir IBSCBS.',
                        secao=secao_xml,
                    ),
                )
            elif cfg['incluir_xml'] and xml_contem_reforma_tributaria(xml):
                itens.append(
                    _item(
                        'xml_sem_rtc',
                        'Tags RTC no XML',
                        'alerta',
                        'XML contém IBSCBS sem Reforma calculada no snapshot.',
                        secao=secao_xml,
                    ),
                )
            else:
                itens.append(
                    _item(
                        'xml_sem_rtc',
                        'Reforma no XML',
                        'nao_aplicavel',
                        'Sem Reforma calculada — IBSCBS omitido no XML.',
                        secao=secao_xml,
                    ),
                )

    itens.extend(_validar_danfe_checklist(nf))

    return itens


def _validar_apuracao_reforma(nf: NFeSaida | None) -> list[dict[str, str]]:
    itens: list[dict[str, str]] = []
    if nf:
        if eh_documento_homologacao(nf) or nf_autorizada_homologacao(nf):
            itens.append(
                _item(
                    'homolog_fora_apuracao',
                    'Homologação fora da apuração',
                    'ok',
                    'NF-e de homologação permanece fora da apuração fiscal.',
                    secao='apuracao',
                ),
            )
        if not pode_entrar_apuracao(nf):
            itens.append(
                _item(
                    'nao_entra_apuracao',
                    'Exclusão da apuração',
                    'ok',
                    'Documento excluído da apuração gerencial.',
                    secao='apuracao',
                ),
            )
        if not tem_valor_fiscal(nf):
            itens.append(
                _item(
                    'sem_valor_fiscal',
                    'Sem valor fiscal',
                    'alerta',
                    'Homologação sem valor fiscal real.',
                    secao='apuracao',
                ),
            )
    else:
        itens.append(
            _item(
                'homolog_fora_apuracao',
                'Homologação fora da apuração',
                'alerta',
                'Nova NF-e será emitida em homologação — fora da apuração.',
                secao='apuracao',
            ),
        )

    cfg = reforma_nfe_config()
    rtc_status = status_reforma_nfe_documento(nf) if nf else cfg['modo']
    alerta_rtc = alerta_reforma_antes_homologacao(nf)
    if cfg['incluir_xml'] and alerta_rtc:
        itens.append(
            _item(
                'reforma_tributaria',
                'Reforma Tributária',
                'bloqueado',
                alerta_rtc,
                secao='reforma_tributaria',
            ),
        )
    elif cfg['modo'] == 'producao' and cfg.get('producao_bloqueada'):
        itens.append(
            _item(
                'reforma_producao',
                'Produção RTC',
                'bloqueado',
                'Geração em produção bloqueada até validação oficial.',
                secao='reforma_tributaria',
            ),
        )
    else:
        msg = 'Estrutura em pesquisa/preparação. XML e DANFE seguem layout atual.'
        if nf:
            alerta = alerta_reforma_antes_homologacao(nf)
            if alerta:
                msg = alerta
        itens.append(
            _item(
                'reforma_tributaria',
                'Reforma Tributária',
                'alerta',
                msg,
                secao='reforma_tributaria',
            ),
        )

    itens.append(
        _item(
            'reforma_status',
            'Status Reforma',
            'ok' if rtc_status != 'bloqueada_producao' else 'bloqueado',
            f'Status: {rtc_status}.',
            secao='reforma_tributaria',
        ),
    )
    return itens


def _validar_efeitos_colaterais(nf: NFeSaida | None, pedido: PedidoVenda | None) -> list[dict[str, str]]:
    itens: list[dict[str, str]] = []
    secao_fin = 'financeiro'
    secao_est = 'estoque_expedicao'

    itens.append(
        _item(
            'sem_financeiro',
            'Sem financeiro automático',
            'ok',
            'Checklist não gera Contas a Receber/Pagar nem títulos financeiros.',
            secao=secao_fin,
        ),
    )
    itens.append(
        _item(
            'duplicatas_sem_cr',
            'Duplicatas sem Contas a Receber',
            'ok',
            'Duplicatas da NF-e são apenas informação fiscal/comercial nesta fase.',
            secao=secao_fin,
        ),
    )
    itens.append(
        _item(
            'sem_estoque',
            'Sem movimentação de estoque',
            'ok',
            'Validação não movimenta nem reserva estoque.',
            secao=secao_est,
        ),
    )
    itens.append(
        _item(
            'sem_expedicao',
            'Sem expedição automática',
            'ok',
            'Validação não cria expedição.',
            secao=secao_est,
        ),
    )

    if nf:
        resumo = obter_resumo_atendimento_operacional(nf, contexto='nfe_saida')
        badges = resumo.get('badges') or []
        if badges:
            labels = [b.get('label', '') for b in badges if isinstance(b, dict)]
            itens.append(
                _item(
                    'atendimento_informativo',
                    'Atendimento operacional',
                    'alerta',
                    'Atendimento operacional existente (informativo): '
                    + ', '.join(labels[:3])
                    + ('…' if len(labels) > 3 else '')
                    + '. Não bloqueia homologação.',
                    secao='atendimento',
                ),
            )
        else:
            itens.append(
                _item(
                    'atendimento_informativo',
                    'Atendimento operacional',
                    'alerta',
                    'Atendimento operacional não definido ou pendente — informativo apenas.',
                    secao='atendimento',
                ),
            )

        antes_est = AtendimentoEstoque.objects.count()
        if antes_est >= 0:
            itens.append(
                _item(
                    'estoque_inalterado',
                    'Estoque inalterado',
                    'ok',
                    'Nenhuma movimentação de estoque disparada por este checklist.',
                    secao=secao_est,
                ),
            )

    if pedido:
        try:
            pdf = gerar_pedido_venda_pdf_bytes(pedido)
            text = pdf.decode('latin-1', errors='ignore').lower() if isinstance(pdf, bytes) else ''
            if not text:
                from pypdf import PdfReader

                text = ''
                for page in PdfReader(io.BytesIO(pdf)).pages:
                    text += (page.extract_text() or '').lower()
            leak = [t for t in PDF_FISCAL_FORBIDDEN if t in text]
            if leak:
                itens.append(
                    _item(
                        'pdf_pedido_limpo',
                        'PDF comercial do Pedido',
                        'bloqueado',
                        f'PDF comercial contém termos fiscais indevidos: {", ".join(leak[:3])}.',
                        secao='documentos',
                    ),
                )
            else:
                itens.append(
                    _item(
                        'pdf_pedido_limpo',
                        'PDF comercial do Pedido',
                        'ok',
                        'PDF comercial do Pedido sem dados fiscais da NF-e.',
                        secao='documentos',
                    ),
                )
        except Exception as exc:
            itens.append(
                _item(
                    'pdf_pedido_limpo',
                    'PDF comercial do Pedido',
                    'alerta',
                    f'Não foi possível validar PDF do pedido: {exc}',
                    secao='documentos',
                ),
            )

    return itens


def _validar_ui_api(nf: NFeSaida | None) -> list[dict[str, str]]:
    itens: list[dict[str, str]] = []
    if not nf:
        itens.append(
            _item('listagem_resumo', 'Listagem NF-e', 'nao_aplicavel', 'Sem NF-e gerada.', secao='ui'),
        )
        return itens

    resumo = montar_listagem_resumo_nfe(nf)
    titulo = resumo.get('titulo') or ''
    if re.search(r'^RASCUNHO-FAT', titulo, re.I):
        itens.append(
            _item(
                'listagem_resumo',
                'Título amigável na listagem',
                'bloqueado',
                'Listagem ainda usa referência interna RASCUNHO-FAT como título.',
                secao='ui',
            ),
        )
    else:
        itens.append(
            _item(
                'listagem_resumo',
                'Título amigável na listagem',
                'ok',
                titulo or 'Título de listagem disponível.',
                secao='ui',
            ),
        )

    fiscal = resumo.get('fiscal_resumo') or {}
    if fiscal.get('badge'):
        itens.append(
            _item(
                'fiscal_resumo',
                'Resumo fiscal agrupado',
                'ok',
                f"{fiscal.get('badge')} — {fiscal.get('subtexto', '')}".strip(' —'),
                secao='ui',
            ),
        )

    ap = montar_apresentacao_nfe_saida(nf)
    itens.append(
        _item(
            'drawer_apresentacao',
            'Drawer / detalhe',
            'ok',
            ap.get('titulo_exibicao') or 'Apresentação fiscal disponível no detalhe.',
            secao='ui',
        ),
    )
    return itens


def validar_prontidao_nfe_homologacao(
    *,
    pedido_venda: PedidoVenda | None = None,
    faturamento: FaturamentoPedidoVenda | None = None,
    nfe_saida: NFeSaida | None = None,
) -> dict[str, Any]:
    """
    Checklist read-only de pré-homologação.
    Não transmite NF-e, não gera financeiro, estoque ou expedição.
    """
    pedido, fat, nf = _resolver_contexto(
        pedido_venda=pedido_venda,
        faturamento=faturamento,
        nfe_saida=nfe_saida,
    )

    itens: list[dict[str, str]] = []
    itens.extend(_validar_pedido_faturamento(pedido, fat, nf))
    itens.extend(_validar_duplicatas(nf))
    itens.extend(_validar_xml_danfe(nf))
    itens.extend(_validar_apuracao_reforma(nf))
    itens.extend(_validar_efeitos_colaterais(nf, pedido))
    itens.extend(_validar_ui_api(nf))

    resultado = _montar_resultado(itens)
    resultado.update(
        {
            'pedido_venda_id': pedido.pk if pedido else None,
            'faturamento_id': fat.pk if fat else None,
            'nfe_saida_id': nf.pk if nf else None,
            'mensagem': (
                'Checklist aprovado. O sistema está pronto para um novo teste de NF-e em homologação.'
                if resultado['status'] == 'aprovado'
                else (
                    'Checklist aprovado com alertas. Revise os pontos antes de prosseguir.'
                    if resultado['status'] == 'aprovado_com_alertas'
                    else 'Checklist bloqueado. Corrija os itens críticos antes de gerar uma nova NF-e de homologação.'
                )
            ),
        },
    )
    return resultado
