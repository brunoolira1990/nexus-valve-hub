"""Exportação de XMLs fiscais por período — módulo Contador."""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
)


class ContadorExportacaoError(Exception):
    pass


MAX_DIAS_PERIODO = 366
TIPOS_VALIDOS = frozenset({'nfe_saida', 'nfe_entrada', 'cte', 'todos'})


def _parse_data(valor: str, *, campo: str) -> date:
    try:
        return date.fromisoformat(str(valor).strip())
    except (TypeError, ValueError) as exc:
        raise ContadorExportacaoError(f'{campo} inválida. Use o formato AAAA-MM-DD.') from exc


def validar_parametros_exportacao(*, inicio: str, fim: str, tipo: str) -> tuple[date, date, str]:
    if not inicio or not fim:
        raise ContadorExportacaoError('Informe data inicial e final.')
    d_ini = _parse_data(inicio, campo='Data inicial')
    d_fim = _parse_data(fim, campo='Data final')
    if d_fim < d_ini:
        raise ContadorExportacaoError('Data final deve ser igual ou posterior à inicial.')
    if (d_fim - d_ini).days > MAX_DIAS_PERIODO:
        raise ContadorExportacaoError(f'Período máximo de {MAX_DIAS_PERIODO} dias.')
    tipo_norm = (tipo or 'todos').strip().lower()
    if tipo_norm not in TIPOS_VALIDOS:
        raise ContadorExportacaoError('Tipo inválido. Use nfe_saida, nfe_entrada, cte ou todos.')
    return d_ini, d_fim, tipo_norm


def _xml_nfe_saida(nf: NFeSaida) -> str:
    xml = (nf.xml_autorizado or '').strip()
    if xml:
        return xml
    try:
        from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe

        xml = resolver_xml_autorizado_danfe(nf, persistir=False)
    except Exception:
        xml = ''
    return xml.strip() if xml else ''


def _nome_arquivo(chave: str, prefixo: str, pk: int) -> str:
    base = (chave or '').strip() or f'{prefixo}-{pk}'
    return f'{base}.xml'


def _coletar_nfe_saida(d_ini: date, d_fim: date) -> list[tuple[str, str]]:
    arquivos: list[tuple[str, str]] = []
    qs = NFeSaida.objects.filter(data__gte=d_ini, data__lte=d_fim).only(
        'id', 'chave_acesso', 'numero', 'xml_autorizado',
        'xml_assinado', 'xml_nfe_gerado', 'xml_envio', 'xml_retorno', 'xml_protocolo',
    )
    for nf in qs.iterator(chunk_size=200):
        xml = _xml_nfe_saida(nf)
        if not xml:
            continue
        chave = getattr(nf, 'chave_acesso', '') or f'NFE-SAIDA-{nf.numero or nf.pk}'
        arquivos.append((_nome_arquivo(chave, 'NFE-SAIDA', nf.pk), xml))
    return arquivos


def _coletar_nfe_entrada(d_ini: date, d_fim: date) -> list[tuple[str, str]]:
    arquivos: list[tuple[str, str]] = []
    qs = NFeEntrada.objects.filter(data__gte=d_ini, data__lte=d_fim).only(
        'id', 'chave_acesso', 'numero', 'xml_importado',
    )
    for nf in qs.iterator(chunk_size=200):
        xml = (nf.xml_importado or '').strip()
        if not xml:
            continue
        chave = nf.chave_acesso or f'NFE-ENTRADA-{nf.numero or nf.pk}'
        arquivos.append((_nome_arquivo(chave, 'NFE-ENTRADA', nf.pk), xml))

    tz = timezone.get_current_timezone()
    ini_dt = timezone.make_aware(datetime.combine(d_ini, time.min), tz)
    fim_dt = timezone.make_aware(datetime.combine(d_fim, time.max), tz)
    hist = NFeEntradaHistoricaImportada.objects.filter(
        dh_emissao__gte=ini_dt,
        dh_emissao__lte=fim_dt,
    ).only('id', 'chave_acesso', 'numero', 'xml_conteudo')
    for doc in hist.iterator(chunk_size=200):
        xml = (doc.xml_conteudo or '').strip()
        if not xml:
            continue
        arquivos.append((_nome_arquivo(doc.chave_acesso, 'NFE-ENTRADA-BASE', doc.pk), xml))
    return arquivos


def _coletar_cte(d_ini: date, d_fim: date) -> list[tuple[str, str]]:
    arquivos: list[tuple[str, str]] = []
    tz = timezone.get_current_timezone()
    ini_dt = timezone.make_aware(datetime.combine(d_ini, time.min), tz)
    fim_dt = timezone.make_aware(datetime.combine(d_fim, time.max), tz)
    qs = CTeHistoricoImportado.objects.filter(
        dh_emissao__gte=ini_dt,
        dh_emissao__lte=fim_dt,
    ).only('id', 'chave_acesso', 'numero', 'xml_conteudo')
    for cte in qs.iterator(chunk_size=200):
        xml = (cte.xml_conteudo or '').strip()
        if not xml:
            continue
        chave = cte.chave_acesso or f'CTE-{cte.numero or cte.pk}'
        arquivos.append((_nome_arquivo(chave, 'CTE', cte.pk), xml))
    return arquivos


def coletar_xmls_periodo(*, inicio: date, fim: date, tipo: str) -> list[tuple[str, str]]:
    arquivos: list[tuple[str, str]] = []
    if tipo in ('nfe_saida', 'todos'):
        arquivos.extend(_coletar_nfe_saida(inicio, fim))
    if tipo in ('nfe_entrada', 'todos'):
        arquivos.extend(_coletar_nfe_entrada(inicio, fim))
    if tipo in ('cte', 'todos'):
        arquivos.extend(_coletar_cte(inicio, fim))
    return arquivos


def montar_zip_xmls(*, inicio: date, fim: date, tipo: str) -> tuple[bytes, str]:
    arquivos = coletar_xmls_periodo(inicio=inicio, fim=fim, tipo=tipo)
    if not arquivos:
        raise ContadorExportacaoError('Nenhum XML encontrado para o período e tipo informados.')

    usados: set[str] = set()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in arquivos:
            nome_zip = nome
            if nome_zip in usados:
                base, ext = nome.rsplit('.', 1) if '.' in nome else (nome, 'xml')
                idx = 2
                while f'{base}-{idx}.{ext}' in usados:
                    idx += 1
                nome_zip = f'{base}-{idx}.{ext}'
            usados.add(nome_zip)
            zf.writestr(nome_zip, conteudo.encode('utf-8'))

    nome_zip = f'nexus-xmls-{inicio.isoformat()}-{fim.isoformat()}-{tipo}.zip'
    return buffer.getvalue(), nome_zip
