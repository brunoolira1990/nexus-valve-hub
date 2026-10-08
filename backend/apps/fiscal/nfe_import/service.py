from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction

from apps.cadastros.models import Cliente

from ..models import (
    EventoNFeSaidaHistoricaImportada,
    EventoNFeSaidaHistoricaPendente,
    ItemNFeSaidaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)
from ..nfe_historica_classificacao import classificar_por_empresa, eh_entrada_propria_ja_emitida, norm_digits
from .service_entrada_propria import mensagem_rejeicao_entrada_propria_em_outro_fluxo
from ..services.reforma_tributaria import enriquecer_reforma_e_outros_json_nf
from .falha_xml import falha_com_traceback, montar_falha_importacao_xml, normalizar_tipo_documento_api
from .parser import ParsedNFeEvento, ParsedNFeImport, extract_dest_documento, parse_xml_nfe_importacao
from .parser_entrada import parse_nfe_entrada_xml


def _chave_from_parsed(parsed: ParsedNFeImport) -> str:
    if parsed.nfe and (parsed.nfe.chave_acesso or '').strip():
        return parsed.nfe.chave_acesso.strip()
    if parsed.evento and (parsed.evento.chave_acesso or '').strip():
        return parsed.evento.chave_acesso.strip()
    return ''


def _tipo_doc_api(parsed: ParsedNFeImport) -> str:
    ec = bool(parsed.evento and parsed.evento.evento_cancelamento)
    return normalizar_tipo_documento_api(parsed.tipo_documento, evento_cancelamento=ec)


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


def _iso_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _payload_evento_aplicado(
    *,
    arquivo: str,
    nf: NFeSaidaHistoricaImportada,
    tipo_evento: str,
    protocol: str,
    origem: str = 'importacao',
) -> dict[str, Any]:
    return {
        'arquivo': arquivo,
        'id_nota': nf.id,
        'chave_acesso': nf.chave_acesso,
        'tipo_evento': tipo_evento,
        'protocolo_evento': protocol,
        'tipo_documento': 'evento',
        'origem': origem,
    }


def _aplicar_cancelamento_em_nf(
    nf: NFeSaidaHistoricaImportada,
    *,
    chave_acesso: str,
    tipo_evento: str,
    protocol: str,
    event_id: str,
    sequencial_evento: int,
    data_evento: datetime | None,
    evento_json: dict[str, Any],
    nome_arquivo: str,
) -> None:
    EventoNFeSaidaHistoricaImportada.objects.create(
        nf=nf,
        chave_acesso=chave_acesso,
        tipo_evento=tipo_evento[:16],
        protocolo_evento=protocol,
        id_evento=event_id,
        sequencial_evento=sequencial_evento,
        data_evento=data_evento,
        evento_json=evento_json,
        nome_arquivo=nome_arquivo[:255],
    )
    nf.cancelada = True
    nf.status_documento = 'cancelada'
    nf.data_cancelamento = data_evento or nf.data_cancelamento
    nf.protocolo_evento = protocol
    nf.tipo_evento = tipo_evento[:16]
    nf.evento_cancelamento_json = evento_json
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


def _serializar_evento_pendente_api(p: EventoNFeSaidaHistoricaPendente, arquivo: str = '') -> dict[str, Any]:
    return {
        'id': p.id,
        'arquivo': arquivo or p.nome_arquivo,
        'chave_nfe': p.chave_nfe,
        'tipo_evento': p.tipo_evento,
        'descricao_evento': p.descricao_evento,
        'sequencia_evento': p.sequencia_evento,
        'data_evento': _iso_dt(p.data_evento),
        'protocolo_evento': p.protocolo_evento,
        'mensagem': p.mensagem,
        'acao_sugerida': (
            'Importe o XML completo da NF-e correspondente ou mantenha o evento pendente para conciliação posterior.'
        ),
        'situacao': 'EVENTO_PENDENTE',
        'status': p.status,
    }


def _salvar_evento_cancelamento_pendente(
    *,
    nome: str,
    parsed_evento: ParsedNFeEvento,
) -> EventoNFeSaidaHistoricaPendente:
    protocol = (parsed_evento.protocolo_evento or '')[:30]
    event_id = (parsed_evento.id_evento or '')[:80]
    msg = 'Evento recebido, mas a NF-e correspondente ainda não foi importada.'
    pend, _created = EventoNFeSaidaHistoricaPendente.objects.update_or_create(
        chave_nfe=parsed_evento.chave_acesso,
        tipo_evento=parsed_evento.tipo_evento[:16],
        protocolo_evento=protocol,
        id_evento=event_id,
        defaults={
            'descricao_evento': (parsed_evento.desc_evento or '')[:255],
            'sequencia_evento': parsed_evento.sequencial_evento,
            'data_evento': parsed_evento.data_evento,
            'justificativa': (parsed_evento.x_just or '')[:4000],
            'evento_json': parsed_evento.evento_json,
            'nome_arquivo': nome[:255],
            'mensagem': msg,
            'status': EventoNFeSaidaHistoricaPendente.Status.PENDENTE,
            'nf': None,
        },
    )
    return pend


def _tentar_aplicar_pendentes_para_nf(
    nf: NFeSaidaHistoricaImportada,
    eventos_aplicados: list[dict[str, Any]],
) -> None:
    pendentes = EventoNFeSaidaHistoricaPendente.objects.filter(
        chave_nfe=nf.chave_acesso,
        status=EventoNFeSaidaHistoricaPendente.Status.PENDENTE,
        tipo_evento='110111',
    )
    for pend in pendentes:
        protocol = (pend.protocolo_evento or '')[:30]
        event_id = (pend.id_evento or '')[:80]
        if EventoNFeSaidaHistoricaImportada.objects.filter(
            nf=nf,
            tipo_evento=pend.tipo_evento[:16],
            protocolo_evento=protocol,
            id_evento=event_id,
        ).exists():
            pend.status = EventoNFeSaidaHistoricaPendente.Status.APLICADO
            pend.nf = nf
            pend.save(update_fields=['status', 'nf', 'atualizado_em'])
            continue
        try:
            with transaction.atomic():
                _aplicar_cancelamento_em_nf(
                    nf,
                    chave_acesso=pend.chave_nfe,
                    tipo_evento=pend.tipo_evento,
                    protocol=protocol,
                    event_id=event_id,
                    sequencial_evento=pend.sequencia_evento,
                    data_evento=pend.data_evento,
                    evento_json=pend.evento_json or {},
                    nome_arquivo=pend.nome_arquivo or 'pendente.xml',
                )
                pend.status = EventoNFeSaidaHistoricaPendente.Status.APLICADO
                pend.nf = nf
                pend.save(update_fields=['status', 'nf', 'atualizado_em'])
        except Exception:
            continue
        eventos_aplicados.append(
            _payload_evento_aplicado(
                arquivo=pend.nome_arquivo or 'pendente.xml',
                nf=nf,
                tipo_evento=pend.tipo_evento,
                protocol=protocol,
                origem='pendente_apos_nf',
            )
        )


def reprocessar_eventos_pendentes_saida() -> dict[str, Any]:
    """Tenta aplicar cancelamentos pendentes quando a NF-e correspondente já existir."""
    aplicados = 0
    permanecem = 0
    detalhes: list[dict[str, Any]] = []
    pendentes = EventoNFeSaidaHistoricaPendente.objects.filter(
        status=EventoNFeSaidaHistoricaPendente.Status.PENDENTE,
        tipo_evento='110111',
    ).order_by('id')
    for pend in pendentes:
        nf = NFeSaidaHistoricaImportada.objects.filter(chave_acesso=pend.chave_nfe).first()
        if nf is None:
            permanecem += 1
            detalhes.append({'chave_nfe': pend.chave_nfe, 'resultado': 'pendente', 'motivo': 'NF-e não encontrada'})
            continue
        protocol = (pend.protocolo_evento or '')[:30]
        event_id = (pend.id_evento or '')[:80]
        if EventoNFeSaidaHistoricaImportada.objects.filter(
            nf=nf,
            tipo_evento=pend.tipo_evento[:16],
            protocolo_evento=protocol,
            id_evento=event_id,
        ).exists():
            pend.status = EventoNFeSaidaHistoricaPendente.Status.APLICADO
            pend.nf = nf
            pend.save(update_fields=['status', 'nf', 'atualizado_em'])
            aplicados += 1
            detalhes.append({'chave_nfe': pend.chave_nfe, 'resultado': 'ja_registrado', 'id_nota': nf.id})
            continue
        try:
            with transaction.atomic():
                _aplicar_cancelamento_em_nf(
                    nf,
                    chave_acesso=pend.chave_nfe,
                    tipo_evento=pend.tipo_evento,
                    protocol=protocol,
                    event_id=event_id,
                    sequencial_evento=pend.sequencia_evento,
                    data_evento=pend.data_evento,
                    evento_json=pend.evento_json or {},
                    nome_arquivo=pend.nome_arquivo or 'reprocessamento.xml',
                )
                pend.status = EventoNFeSaidaHistoricaPendente.Status.APLICADO
                pend.nf = nf
                pend.save(update_fields=['status', 'nf', 'atualizado_em'])
        except Exception as exc:
            permanecem += 1
            detalhes.append({'chave_nfe': pend.chave_nfe, 'resultado': 'erro', 'detalhe': str(exc)})
            continue
        aplicados += 1
        detalhes.append({'chave_nfe': pend.chave_nfe, 'resultado': 'aplicado', 'id_nota': nf.id})
    return {'aplicados': aplicados, 'permanecem_pendentes': permanecem, 'detalhes': detalhes}


def importar_arquivos(arquivos: list[tuple[str, bytes]]) -> dict[str, Any]:
    importadas: list[dict[str, Any]] = []
    duplicadas: list[dict[str, Any]] = []
    eventos_aplicados: list[dict[str, Any]] = []
    eventos_duplicados: list[dict[str, Any]] = []
    eventos_pendentes: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []

    for nome, conteudo in arquivos:
        nome = nome or 'sem_nome.xml'
        parsed = parse_xml_nfe_importacao(conteudo)
        if parsed.erro:
            if parsed.tipo_documento == 'nfe':
                entrada_parsed = parse_nfe_entrada_xml(conteudo)
                if not entrada_parsed.erro:
                    is_propria, _emp = eh_entrada_propria_ja_emitida(
                        entrada_parsed.emit_json,
                        entrada_parsed.dest_json,
                        tp_nf=entrada_parsed.tp_nf,
                    )
                    if is_propria:
                        msg, acao = mensagem_rejeicao_entrada_propria_em_outro_fluxo()
                        erros.append(
                            montar_falha_importacao_xml(
                                arquivo=nome,
                                chave=entrada_parsed.chave_acesso,
                                tipo_documento='NFE',
                                tipo_erro='Classificação / cadastro',
                                mensagem_completa=msg,
                                acao_sugerida=acao,
                            )
                        )
                        continue
            ch = _chave_from_parsed(parsed)
            td = _tipo_doc_api(parsed)
            te = (
                'Leitura XML'
                if ('XML inválido' in parsed.erro or 'corrompido' in parsed.erro)
                else 'Validação da NF-e / evento'
            )
            acao = (
                'Verifique encoding, integridade do arquivo e se o conteúdo é XML de NF-e (infNFe) '
                'ou procEventoNFe/evento com estrutura SEFAZ.'
            )
            if td in {'EVENTO', 'CANCELAMENTO'}:
                acao = (
                    'Para eventos, use o XML completo (procEventoNFe). chNFe deve ter 44 dígitos. '
                    'Cancelamento (110111) só aplica se a NF-e principal já existir nesta base.'
                )
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=ch,
                    tipo_documento=td,
                    tipo_erro=te,
                    mensagem_completa=parsed.erro,
                    acao_sugerida=acao,
                )
            )
            continue

        if parsed.tipo_documento == 'evento' and parsed.evento is not None:
            _importar_evento_cancelamento(
                nome=nome,
                parsed_evento=parsed.evento,
                eventos_aplicados=eventos_aplicados,
                eventos_duplicados=eventos_duplicados,
                eventos_pendentes=eventos_pendentes,
                erros=erros,
            )
            continue

        if parsed.nfe is None:
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave='',
                    tipo_documento='DESCONHECIDO',
                    tipo_erro='Validação da NF-e / evento',
                    mensagem_completa='Arquivo não reconhecido como NF-e nem evento.',
                    acao_sugerida=(
                        'Envie XML de NF-e (raiz NFe ou nfeProc com infNFe) ou XML de evento (procEventoNFe / evento). '
                        'Evite HTML da SEFAZ, PDF ou ZIP sem extrair o XML.'
                    ),
                )
            )
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
        is_propria, _emp = eh_entrada_propria_ja_emitida(
            parsed.nfe.emit_json,
            parsed.nfe.dest_json,
            tp_nf=parsed.nfe.tp_nf,
        )
        if is_propria:
            msg, acao = mensagem_rejeicao_entrada_propria_em_outro_fluxo()
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.nfe.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=msg,
                    acao_sugerida=acao,
                )
            )
            continue
        if classificacao.tipo_fluxo == 'entrada':
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.nfe.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=(
                        'NF-e de compra (destinatário identificado como Empresa cadastrada, emitente externo). '
                        'Importe em NF-e de entrada histórica, não no fluxo de saída / faturamento.'
                    ),
                    acao_sugerida=(
                        'Use a tela "NF-e Entrada Histórica/XML" para compras. O fluxo de saída exige Empresa como emitente do XML.'
                    ),
                )
            )
            continue
        if classificacao.tipo_fluxo != 'saida' or not classificacao.empresa_emitente:
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.nfe.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=(
                        'Classificação bloqueada: não foi possível identificar a Empresa cadastrada como emitente '
                        'ou destinatária do XML por CNPJ. Cadastre a Empresa corretamente para decidir se a NF-e '
                        'é saída (emitente) ou entrada (destinatário).'
                    ),
                    acao_sugerida=(
                        'Conferir CNPJ da Empresa no cadastro (apenas dígitos) e o emit/dest do XML; '
                        'emitente da nota de venda deve bater com uma Empresa cadastrada.'
                    ),
                )
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
                    reforma_e_outros_json=enriquecer_reforma_e_outros_json_nf(
                        parsed.nfe.totais_json, parsed.nfe.reforma_e_outros_json
                    ),
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
                _tentar_aplicar_pendentes_para_nf(nf, eventos_aplicados)
        except Exception as e:
            erros.append(
                falha_com_traceback(
                    arquivo=nome,
                    chave=parsed.nfe.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Gravação no banco',
                    mensagem_completa=f'Falha ao gravar a NF-e importada: {e}',
                    acao_sugerida=(
                        'Verifique logs do servidor, concorrência (importação duplicada simultânea) e integridade do XML. '
                        'Copie o diagnóstico completo para o suporte.'
                    ),
                    exc=e,
                )
            )
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

    n_erros = len(erros)
    n_dup = len(duplicadas)
    n_pend = len(eventos_pendentes)
    return {
        'importadas': importadas,
        'duplicadas': duplicadas,
        'eventos_aplicados': eventos_aplicados,
        'eventos_duplicados': eventos_duplicados,
        'eventos_pendentes': eventos_pendentes,
        'erros': erros,
        'resumo': {
            'total_arquivos': len(arquivos),
            'importadas': len(importadas),
            'importadas_com_advertencia': 0,
            'ja_existiam': n_dup,
            'duplicadas': n_dup,
            'eventos_aplicados': len(eventos_aplicados),
            'eventos_duplicados': len(eventos_duplicados),
            'eventos_pendentes': n_pend,
            'erros': n_erros,
            'falhas': n_erros,
        },
    }


def _importar_evento_cancelamento(
    *,
    nome: str,
    parsed_evento: ParsedNFeEvento,
    eventos_aplicados: list[dict[str, Any]],
    eventos_duplicados: list[dict[str, Any]],
    eventos_pendentes: list[dict[str, Any]],
    erros: list[dict[str, Any]],
) -> None:
    if not parsed_evento.evento_cancelamento:
        erros.append(
            montar_falha_importacao_xml(
                arquivo=nome,
                chave=parsed_evento.chave_acesso,
                tipo_documento='EVENTO',
                tipo_erro='Evento NF-e',
                mensagem_completa=f'Evento {parsed_evento.tipo_evento} ainda não suportado nesta fase.',
                acao_sugerida=(
                    'Somente cancelamento (tpEvento 110111) é tratado nesta versão. '
                    'Para outros eventos, aguarde evolução ou processe manualmente.'
                ),
            )
        )
        return

    nf = NFeSaidaHistoricaImportada.objects.filter(chave_acesso=parsed_evento.chave_acesso).first()
    if nf is None:
        pend = _salvar_evento_cancelamento_pendente(nome=nome, parsed_evento=parsed_evento)
        eventos_pendentes.append(_serializar_evento_pendente_api(pend, arquivo=nome))
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
            _aplicar_cancelamento_em_nf(
                nf,
                chave_acesso=parsed_evento.chave_acesso,
                tipo_evento=parsed_evento.tipo_evento,
                protocol=protocol,
                event_id=event_id,
                sequencial_evento=parsed_evento.sequencial_evento,
                data_evento=parsed_evento.data_evento,
                evento_json=parsed_evento.evento_json,
                nome_arquivo=nome,
            )
    except Exception as e:
        erros.append(
            falha_com_traceback(
                arquivo=nome,
                chave=parsed_evento.chave_acesso,
                tipo_documento='CANCELAMENTO',
                tipo_erro='Gravação no banco',
                mensagem_completa=f'Falha ao aplicar evento de cancelamento: {e}',
                acao_sugerida=(
                    'Verifique duplicidade de protocolo, permissões e logs do servidor. '
                    'Copie o diagnóstico completo (stack) para análise.'
                ),
                exc=e,
            )
        )
        return

    eventos_aplicados.append(
        _payload_evento_aplicado(
            arquivo=nome,
            nf=nf,
            tipo_evento=parsed_evento.tipo_evento,
            protocol=protocol,
            origem='importacao',
        )
    )
