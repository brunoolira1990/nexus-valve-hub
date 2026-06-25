"""Envio manual de DANFE + XML autorizado da NF-e Saída por e-mail próprio."""

from __future__ import annotations

import logging
import re
import smtplib
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

from apps.fiscal.models import NFeSaida, NFeSaidaEnvioEmail
from apps.fiscal.nfe_emissao.consulta_situacao import _homologacao_da_nfe
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import DanfeBfrError
from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe
from apps.fiscal.nfe_saida_arquivo_autorizado import (
    nome_arquivo_danfe_autorizado,
    nome_arquivo_xml_autorizado,
)
from apps.fiscal.nfe_saida_bloqueio import (
    nf_autorizada_homologacao,
    nf_autorizada_producao,
    nf_cancelada_operacional,
)
from apps.fiscal.nfe_saida_danfe_autorizado import gerar_danfe_autorizado_nfe_saida

logger = logging.getLogger(__name__)

_EMAIL_SPLIT_RE = re.compile(r'[;,\s]+')


class NFeEnvioEmailError(ValueError):
    pass


def _fmt_nnf(numero: str | None) -> str:
    digits = ''.join(c for c in str(numero or '') if c.isdigit())
    if not digits:
        return str(numero or '').strip() or '—'
    return digits.lstrip('0') or '0'


def _fmt_serie(serie: str | None) -> str:
    digits = ''.join(c for c in str(serie or '') if c.isdigit())
    return str(int(digits)) if digits else str(serie or '').strip() or '—'


def nf_inutilizada_operacional(nf: NFeSaida) -> bool:
    st = (nf.status or '').strip().upper()
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    return 'INUTILIZ' in st or 'INUTILIZ' in sefaz


def normalizar_lista_emails(valor: str | None) -> list[str]:
    if not valor:
        return []
    out: list[str] = []
    vistos: set[str] = set()
    for parte in _EMAIL_SPLIT_RE.split(str(valor).strip()):
        email = parte.strip()
        if not email:
            continue
        try:
            validate_email(email)
        except ValidationError as exc:
            raise NFeEnvioEmailError(f'E-mail inválido: {email}') from exc
        chave = email.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        out.append(email)
    return out


def resolver_destinatario_email_cliente_nfe(nf: NFeSaida) -> dict[str, Any]:
    """
    Sugestão de destinatário para envio DANFE/XML (somente leitura do cadastro).
    Prioridade: email_nf (fiscal) → email principal → vazio.
    """
    vazio = {
        'destinatario_sugerido': '',
        'cliente_sem_email': True,
        'destinatario_origem': '',
    }
    if not nf.cliente_id:
        return vazio

    cliente = nf.cliente
    if cliente is None:
        from apps.cadastros.models import Cliente

        cliente = Cliente.objects.filter(pk=nf.cliente_id).only('email_nf', 'email').first()
    if cliente is None:
        return vazio

    email_nf = (cliente.email_nf or '').strip()
    if email_nf:
        return {
            'destinatario_sugerido': email_nf,
            'cliente_sem_email': False,
            'destinatario_origem': 'email_nf',
        }

    email = (cliente.email or '').strip()
    if email:
        return {
            'destinatario_sugerido': email,
            'cliente_sem_email': False,
            'destinatario_origem': 'email',
        }

    return vazio


def resolver_email_destinatario_sugerido(nf: NFeSaida) -> str:
    return str(resolver_destinatario_email_cliente_nfe(nf).get('destinatario_sugerido') or '').strip()


def tem_xml_autorizado_disponivel(nf: NFeSaida) -> bool:
    try:
        xml = resolver_xml_autorizado_danfe(nf)
        return bool((xml or '').strip())
    except DanfeBfrError:
        return False
    except Exception:
        logger.exception('Falha ao resolver XML autorizado nfe_id=%s', nf.pk)
        return False


def danfe_anexo_disponivel(nf: NFeSaida) -> bool:
    """Indica se o DANFE pode ser gerado no envio (NF autorizada + XML disponível)."""
    if not (nf_autorizada_homologacao(nf) or nf_autorizada_producao(nf)):
        return False
    return tem_xml_autorizado_disponivel(nf)


def avaliar_envio_email_danfe_xml(nf: NFeSaida) -> tuple[bool, str]:
    if nf_cancelada_operacional(nf):
        return False, 'NF-e cancelada não permite envio de DANFE/XML por e-mail.'
    if nf_inutilizada_operacional(nf):
        return False, 'NF-e inutilizada não permite envio de DANFE/XML por e-mail.'
    if not (nf_autorizada_homologacao(nf) or nf_autorizada_producao(nf)):
        return False, 'Envio disponível apenas para NF-e autorizada na SEFAZ.'
    if not tem_xml_autorizado_disponivel(nf):
        return False, 'XML autorizado não disponível para anexo.'
    if not danfe_anexo_disponivel(nf):
        return False, 'DANFE PDF indisponível para anexo.'
    return True, ''


def montar_assunto_sugerido(nf: NFeSaida, *, homolog: bool) -> str:
    nnf = _fmt_nnf(nf.numero_nfe or nf.numero)
    serie = _fmt_serie(nf.serie_nfe)
    empresa = resolver_empresa_emitente_nfe(nf)
    nome_empresa = (getattr(empresa, 'razao_social', None) or 'Nexus Válvulas').strip()
    if homolog:
        return f'HOMOLOGAÇÃO — NF-e {nnf}/{serie} — Sem valor fiscal'
    return f'NF-e {nnf}/{serie} — {nome_empresa}'


def montar_mensagem_sugerida(nf: NFeSaida, *, homolog: bool) -> str:
    nnf = _fmt_nnf(nf.numero_nfe or nf.numero)
    serie = _fmt_serie(nf.serie_nfe)
    chave = (nf.chave_acesso or '').strip()
    protocolo = (nf.protocolo_autorizacao or '').strip()
    empresa = resolver_empresa_emitente_nfe(nf)
    nome_empresa = (getattr(empresa, 'razao_social', None) or 'Nexus Válvulas').strip()
    cliente = ''
    if nf.cliente_id and nf.cliente:
        cliente = (nf.cliente.razao_social or '').strip()

    linhas = [
        f'Prezado(a) {cliente or "cliente"},' if cliente else 'Prezado(a),',
        '',
        f'Segue em anexo o DANFE (PDF) e o XML autorizado da NF-e nº {nnf}, série {serie}, emitida por {nome_empresa}.',
    ]
    if chave:
        linhas.append(f'Chave de acesso: {chave}')
    if protocolo:
        linhas.append(f'Protocolo de autorização: {protocolo}')
    linhas.append('')
    if homolog:
        linhas.append(
            'Documento emitido em ambiente de homologação, sem valor fiscal. '
            'Não utilize para fins contábeis ou fiscais.',
        )
        linhas.append('')
    linhas.append('Atenciosamente,')
    linhas.append(nome_empresa)
    return '\n'.join(linhas)


def _serializar_ultimo_envio(registro: NFeSaidaEnvioEmail | None) -> dict[str, Any] | None:
    if not registro:
        return None
    usuario = registro.enviado_por
    nome_usuario = ''
    if usuario:
        nome_usuario = (usuario.get_full_name() or usuario.username or '').strip()
    return {
        'id': registro.pk,
        'enviado_em': registro.enviado_em.isoformat() if registro.enviado_em else '',
        'usuario_nome': nome_usuario,
        'destinatario': registro.destinatario,
        'copias': registro.copias,
        'assunto': registro.assunto,
        'status_envio': registro.status_envio,
        'mensagem_erro': registro.mensagem_erro,
        'ambiente': registro.ambiente,
        'anexo_xml': registro.anexo_xml,
        'anexo_danfe_pdf': registro.anexo_danfe_pdf,
    }


def montar_dados_envio_email_danfe_xml(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    pode, motivo = avaliar_envio_email_danfe_xml(nf)
    homolog = _homologacao_da_nfe(nf)
    ambiente = 'homologacao' if homolog else 'producao'
    ok_danfe = danfe_anexo_disponivel(nf) if pode else False
    ultimo = nf.envios_email.order_by('-enviado_em', '-id').first()
    cliente_nome = ''
    if nf.cliente_id and nf.cliente:
        cliente_nome = (nf.cliente.razao_social or '').strip()

    destinatario = resolver_destinatario_email_cliente_nfe(nf)
    aviso_sem_email = ''
    if destinatario['cliente_sem_email'] and nf.cliente_id:
        aviso_sem_email = 'Cliente sem e-mail cadastrado. Informe o destinatário manualmente.'

    return {
        'ok': pode,
        'pode_enviar': pode,
        'motivo_bloqueio': motivo,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if homolog else 'Produção SEFAZ',
        'homologacao': homolog,
        'alerta_homologacao': (
            'NF-e emitida em ambiente de HOMOLOGAÇÃO — sem valor fiscal. '
            'O assunto e a mensagem devem deixar isso explícito.'
            if homolog
            else ''
        ),
        'destinatario_sugerido': destinatario['destinatario_sugerido'],
        'cliente_sem_email': destinatario['cliente_sem_email'],
        'destinatario_origem': destinatario['destinatario_origem'],
        'aviso_sem_email_cliente': aviso_sem_email,
        'assunto_sugerido': montar_assunto_sugerido(nf, homolog=homolog),
        'mensagem_sugerida': montar_mensagem_sugerida(nf, homolog=homolog),
        'anexos': {
            'xml_autorizado': tem_xml_autorizado_disponivel(nf),
            'danfe_pdf': ok_danfe,
        },
        'nfe': {
            'id': nf.pk,
            'numero': _fmt_nnf(nf.numero_nfe or nf.numero),
            'serie': _fmt_serie(nf.serie_nfe),
            'chave_acesso': nf.chave_acesso or '',
            'status': nf.status,
            'status_emissao_sefaz': nf.status_emissao_sefaz or '',
            'cliente_nome': cliente_nome,
            'protocolo_autorizacao': nf.protocolo_autorizacao or '',
        },
        'ultimo_envio': _serializar_ultimo_envio(ultimo),
        'historico_recente': [
            _serializar_ultimo_envio(r)
            for r in nf.envios_email.order_by('-enviado_em', '-id')[:5]
            if _serializar_ultimo_envio(r)
        ],
    }


def _registrar_log_envio(
    *,
    nf: NFeSaida,
    usuario,
    destinatario: str,
    copias: str,
    assunto: str,
    ambiente: str,
    status_envio: str,
    mensagem_erro: str = '',
    anexo_xml: bool = False,
    anexo_danfe_pdf: bool = False,
) -> NFeSaidaEnvioEmail:
    return NFeSaidaEnvioEmail.objects.create(
        nfe_saida=nf,
        enviado_por=usuario,
        destinatario=destinatario,
        copias=copias,
        assunto=assunto[:255],
        ambiente=ambiente,
        status_envio=status_envio,
        mensagem_erro=(mensagem_erro or '')[:2000],
        anexo_xml=anexo_xml,
        anexo_danfe_pdf=anexo_danfe_pdf,
    )


def enviar_email_danfe_xml_nfe_saida(
    nf: NFeSaida,
    *,
    usuario,
    para: str,
    cc: str = '',
    assunto: str,
    mensagem: str,
    confirmar_envio: bool = False,
) -> dict[str, Any]:
    pode, motivo = avaliar_envio_email_danfe_xml(nf)
    if not pode:
        raise NFeEnvioEmailError(motivo)

    if not confirmar_envio:
        raise NFeEnvioEmailError('Confirme o envio antes de transmitir o e-mail.')

    destinatarios = normalizar_lista_emails(para)
    if not destinatarios:
        raise NFeEnvioEmailError('Informe ao menos um destinatário válido.')

    copias_lista = normalizar_lista_emails(cc)
    assunto_limpo = (assunto or '').strip()
    mensagem_limpa = (mensagem or '').strip()
    if not assunto_limpo:
        raise NFeEnvioEmailError('Informe o assunto do e-mail.')
    if not mensagem_limpa:
        raise NFeEnvioEmailError('Informe a mensagem do e-mail.')

    homolog = _homologacao_da_nfe(nf)
    ambiente = 'homologacao' if homolog else 'producao'
    if homolog and 'HOMOLOG' not in assunto_limpo.upper():
        raise NFeEnvioEmailError(
            'Em homologação, o assunto deve indicar HOMOLOGAÇÃO / sem valor fiscal.',
        )

    xml_texto = resolver_xml_autorizado_danfe(nf)
    try:
        pdf_bytes, _meta = gerar_danfe_autorizado_nfe_saida(nf)
    except Exception as exc:
        raise NFeEnvioEmailError('Não foi possível gerar o DANFE PDF para anexo.') from exc
    if not pdf_bytes:
        raise NFeEnvioEmailError('Não foi possível gerar o DANFE PDF para anexo.')
    nome_xml = nome_arquivo_xml_autorizado(nf)
    nome_pdf = nome_arquivo_danfe_autorizado(nf)

    from_email = (getattr(settings, 'NEXUS_EMAIL_OPERACIONAL', None) or settings.DEFAULT_FROM_EMAIL or '').strip()
    if not from_email:
        raise NFeEnvioEmailError('E-mail remetente operacional não configurado no ambiente.')

    email = EmailMessage(
        subject=assunto_limpo,
        body=mensagem_limpa,
        from_email=from_email,
        to=destinatarios,
        cc=copias_lista,
    )
    email.attach(nome_xml, xml_texto.encode('utf-8'), 'application/xml')
    email.attach(nome_pdf, pdf_bytes, 'application/pdf')

    copias_str = ', '.join(copias_lista)
    try:
        email.send(fail_silently=False)
    except (smtplib.SMTPException, OSError, ConnectionError) as exc:
        logger.warning(
            'Falha SMTP envio DANFE/XML NF-e id=%s tipo=%s',
            nf.pk,
            type(exc).__name__,
        )
        registro = _registrar_log_envio(
            nf=nf,
            usuario=usuario,
            destinatario=destinatarios[0],
            copias=copias_str,
            assunto=assunto_limpo,
            ambiente=ambiente,
            status_envio=NFeSaidaEnvioEmail.StatusEnvio.ERRO,
            mensagem_erro='Falha ao enviar e-mail. Verifique a configuração SMTP do ambiente.',
            anexo_xml=True,
            anexo_danfe_pdf=True,
        )
        raise NFeEnvioEmailError(
            'Não foi possível enviar o e-mail. Verifique a configuração SMTP do ambiente.',
        ) from exc

    registro = _registrar_log_envio(
        nf=nf,
        usuario=usuario,
        destinatario=destinatarios[0],
        copias=copias_str,
        assunto=assunto_limpo,
        ambiente=ambiente,
        status_envio=NFeSaidaEnvioEmail.StatusEnvio.SUCESSO,
        anexo_xml=True,
        anexo_danfe_pdf=True,
    )
    logger.info(
        'Envio DANFE/XML NF-e id=%s usuario=%s destinatario=%s ambiente=%s',
        nf.pk,
        getattr(usuario, 'pk', None),
        destinatarios[0],
        ambiente,
    )
    return {
        'ok': True,
        'mensagem': 'E-mail enviado com sucesso.',
        'envio': _serializar_ultimo_envio(registro),
    }
