from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.cadastros.models import Cliente

from ..models import EventoNFeSaidaHistoricaImportada, ItemNFeSaidaHistoricaImportada, NFeSaidaHistoricaImportada
from ..nfe_historica_classificacao import classificar_por_empresa, norm_digits
from .parser import ParsedNFeEvento, extract_dest_documento, parse_xml_nfe_importacao


def _norm_digits(val: str) -> str:
    return norm_digits(val)


def _resolve_cliente(dest: dict[str, Any]) -> Cliente | None:
    doc = extract_dest_documento(dest)
    if len(doc) != 14:
        return None
    for cli in Cliente.objects.only('id', 'cnpj'):
        if _norm_digits(cli.cnpj) == doc:
            return cli
    return None


def importar_arquivos(arquivos: list[tuple[str, bytes]]) -> dict[str, Any]:
    importadas: list[dict[str, Any]] = []
    duplicadas: list[dict[str, Any]] = []
    eventos_aplicados: list[dict[str, Any]] = []
    eventos_duplicados: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []

    for nome, conteudo in arquivos:
        nome = nome or 'sem_nome.xml'
        parsed = parse_xml_nfe_importacao(conteudo)
        if parsed.erro:
            erros.append({'arquivo': nome, 'mensagem': parsed.erro, 'tipo_documento': parsed.tipo_documento or 'desconhecido'})
            continue

        if parsed.tipo_documento == 'evento' and parsed.evento is not None:
            _importar_evento_cancelamento(
                nome=nome,
                parsed_evento=parsed.evento,
                eventos_aplicados=eventos_aplicados,
                eventos_duplicados=eventos_duplicados,
                erros=erros,
            )
            continue

        if parsed.nfe is None:
            erros.append({'arquivo': nome, 'mensagem': 'Arquivo não reconhecido como NF-e nem evento.', 'tipo_documento': 'desconhecido'})
            continue

        if NFeSaidaHistoricaImportada.objects.filter(chave_acesso=parsed.nfe.chave_acesso).exists():
            duplicadas.append(
                {
                    'arquivo': nome,
                    'chave_acesso': parsed.nfe.chave_acesso,
                    'mensagem': 'Esta chave de NF-e já foi importada.',
                    'tipo_documento': 'nfe',
                }
            )
            continue

        classificacao = classificar_por_empresa(parsed.nfe.emit_json, parsed.nfe.dest_json)
        if classificacao.tipo_fluxo == 'entrada':
            erros.append(
                {
                    'arquivo': nome,
                    'mensagem': (
                        'NF-e de compra (destinatário identificado como Empresa cadastrada, emitente externo). '
                        'Importe em NF-e de entrada histórica, não no fluxo de saída / faturamento.'
                    ),
                    'tipo_documento': 'nfe',
                }
            )
            continue
        if classificacao.tipo_fluxo != 'saida' or not classificacao.empresa_emitente:
            erros.append(
                {
                    'arquivo': nome,
                    'mensagem': (
                        'Classificação bloqueada: não foi possível identificar a Empresa cadastrada como emitente '
                        'ou destinatária do XML por CNPJ. Cadastre a Empresa corretamente para decidir se a NF-e '
                        'é saída (emitente) ou entrada (destinatário).'
                    ),
                    'tipo_documento': 'nfe',
                }
            )
            continue

        try:
            with transaction.atomic():
                papel_empresa = 'emitente'
                cliente = None if classificacao.empresa_destinataria else _resolve_cliente(parsed.nfe.dest_json)
                nf = NFeSaidaHistoricaImportada.objects.create(
                    chave_acesso=parsed.nfe.chave_acesso,
                    numero=parsed.nfe.numero[:16],
                    serie=parsed.nfe.serie[:4],
                    modelo=parsed.nfe.modelo[:4],
                    dh_emissao=parsed.nfe.dh_emissao,
                    tp_amb=parsed.nfe.tp_amb[:1],
                    tp_nf=parsed.nfe.tp_nf[:1],
                    nat_op=parsed.nfe.nat_op[:120],
                    versao_layout=parsed.nfe.versao_layout[:16],
                    cstat=parsed.nfe.cstat[:8],
                    xmotivo=parsed.nfe.xmotivo[:255],
                    protocolo=parsed.nfe.protocolo[:30],
                    valor_produtos=parsed.nfe.valor_produtos,
                    valor_total_nf=parsed.nfe.valor_total_nf,
                    v_frete=parsed.nfe.v_frete,
                    v_seg=parsed.nfe.v_seg,
                    v_desc=parsed.nfe.v_desc,
                    v_outro=parsed.nfe.v_outro,
                    emit_json=parsed.nfe.emit_json,
                    dest_json=parsed.nfe.dest_json,
                    totais_json=parsed.nfe.totais_json,
                    reforma_e_outros_json=parsed.nfe.reforma_e_outros_json,
                    prot_json=parsed.nfe.prot_json,
                    nome_arquivo=nome[:255],
                    empresa_emitente=classificacao.empresa_emitente,
                    cliente=cliente,
                    papel_empresa_no_documento=papel_empresa,
                )
                bulk = [
                    ItemNFeSaidaHistoricaImportada(
                        nf=nf,
                        n_item=it['n_item'],
                        prod_json=it.get('prod') or {},
                        imposto_json=it.get('imposto') or {},
                    )
                    for it in parsed.nfe.itens
                ]
                ItemNFeSaidaHistoricaImportada.objects.bulk_create(bulk)
        except Exception as e:
            erros.append({'arquivo': nome, 'mensagem': f'Falha ao gravar: {e}', 'tipo_documento': 'nfe'})
            continue

        importadas.append(
            {
                'arquivo': nome,
                'id': nf.id,
                'chave_acesso': nf.chave_acesso,
                'numero': nf.numero,
                'serie': nf.serie,
                'tipo_documento': 'nfe',
            }
        )

    return {
        'importadas': importadas,
        'duplicadas': duplicadas,
        'eventos_aplicados': eventos_aplicados,
        'eventos_duplicados': eventos_duplicados,
        'erros': erros,
        'resumo': {
            'total_arquivos': len(arquivos),
            'importadas': len(importadas),
            'duplicadas': len(duplicadas),
            'eventos_aplicados': len(eventos_aplicados),
            'eventos_duplicados': len(eventos_duplicados),
            'erros': len(erros),
        },
    }


def _importar_evento_cancelamento(
    *,
    nome: str,
    parsed_evento: ParsedNFeEvento,
    eventos_aplicados: list[dict[str, Any]],
    eventos_duplicados: list[dict[str, Any]],
    erros: list[dict[str, Any]],
) -> None:
    if not parsed_evento.evento_cancelamento:
        erros.append(
            {
                'arquivo': nome,
                'chave_acesso': parsed_evento.chave_acesso,
                'mensagem': f'Evento {parsed_evento.tipo_evento} ainda não suportado nesta fase.',
                'tipo_documento': 'evento',
            }
        )
        return

    nf = NFeSaidaHistoricaImportada.objects.filter(chave_acesso=parsed_evento.chave_acesso).first()
    if nf is None:
        erros.append(
            {
                'arquivo': nome,
                'chave_acesso': parsed_evento.chave_acesso,
                'mensagem': 'Evento de cancelamento não aplicado: NF-e histórica correspondente não foi encontrada.',
                'tipo_documento': 'evento',
            }
        )
        return

    protocol = parsed_evento.protocolo_evento[:30]
    event_id = parsed_evento.id_evento[:80]
    already = EventoNFeSaidaHistoricaImportada.objects.filter(
        nf=nf,
        tipo_evento=parsed_evento.tipo_evento[:16],
        protocolo_evento=protocol,
        id_evento=event_id,
    ).exists()
    if already:
        eventos_duplicados.append(
            {
                'arquivo': nome,
                'chave_acesso': parsed_evento.chave_acesso,
                'tipo_evento': parsed_evento.tipo_evento,
                'mensagem': 'Evento de cancelamento já havia sido importado para esta NF-e.',
            }
        )
        return

    try:
        with transaction.atomic():
            EventoNFeSaidaHistoricaImportada.objects.create(
                nf=nf,
                chave_acesso=parsed_evento.chave_acesso,
                tipo_evento=parsed_evento.tipo_evento[:16],
                protocolo_evento=protocol,
                id_evento=event_id,
                sequencial_evento=parsed_evento.sequencial_evento,
                data_evento=parsed_evento.data_evento,
                evento_json=parsed_evento.evento_json,
                nome_arquivo=nome[:255],
            )
            nf.cancelada = True
            nf.status_documento = 'cancelada'
            nf.data_cancelamento = parsed_evento.data_evento or nf.data_cancelamento
            nf.protocolo_evento = protocol
            nf.tipo_evento = parsed_evento.tipo_evento[:16]
            nf.evento_cancelamento_json = parsed_evento.evento_json
            nf.evento_cancelamento_id = event_id
            nf.save(
                update_fields=[
                    'cancelada',
                    'status_documento',
                    'data_cancelamento',
                    'protocolo_evento',
                    'tipo_evento',
                    'evento_cancelamento_json',
                    'evento_cancelamento_id',
                ]
            )
    except Exception as e:
        erros.append(
            {
                'arquivo': nome,
                'chave_acesso': parsed_evento.chave_acesso,
                'mensagem': f'Falha ao aplicar evento de cancelamento: {e}',
                'tipo_documento': 'evento',
            }
        )
        return

    eventos_aplicados.append(
        {
            'arquivo': nome,
            'id_nota': nf.id,
            'chave_acesso': nf.chave_acesso,
            'tipo_evento': parsed_evento.tipo_evento,
            'protocolo_evento': protocol,
            'tipo_documento': 'evento',
        }
    )
