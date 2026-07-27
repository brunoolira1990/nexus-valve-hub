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

MSG_SMTP_FALHA = 'Falha ao enviar e-mail. Verifique a configuração SMTP do ambiente.'
MSG_CC_MULTI = 'O campo CC não pode ser usado no envio para múltiplos destinatários.'
MSG_CONFLITO_DESTINATARIOS = (
    'Os campos para e destinatarios estão em conflito. '
    'Informe apenas um conjunto coerente de destinatários.'
)


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
        chave = email.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        out.append(email)
    return out


def normalizar_lista_emails_de_payload(valor: Any) -> list[str]:
    """Aceita lista JSON ou string (vírgula/ponto-e-vírgula/espaço)."""
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        out: list[str] = []
        vistos: set[str] = set()
        for item in valor:
            email = str(item or '').strip()
            if not email:
                continue
            try:
                validate_email(email)
            except ValidationError as exc:
                raise NFeEnvioEmailError(f'E-mail inválido: {email}') from exc
            chave = email.casefold()
            if chave in vistos:
                continue
            vistos.add(chave)
            out.append(email)
        return out
    return normalizar_lista_emails(str(valor))


def _carregar_cliente_nfe(nf: NFeSaida):
    if not nf.cliente_id:
        return None
    cliente = nf.cliente
    if cliente is None:
        from apps.cadastros.models import Cliente

        cliente = (
            Cliente.objects.filter(pk=nf.cliente_id)
            .prefetch_related('contatos')
            .first()
        )
    return cliente


def resolver_destinatario_email_cliente_nfe(nf: NFeSaida) -> dict[str, Any]:
    """
    Sugestão legada de um destinatário (compatibilidade).
    Prioridade: email_nf → email principal → vazio.
    """
    vazio = {
        'destinatario_sugerido': '',
        'cliente_sem_email': True,
        'destinatario_origem': '',
    }
    cliente = _carregar_cliente_nfe(nf)
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


def montar_destinatarios_sugeridos(nf: NFeSaida) -> list[dict[str, Any]]:
    """
    Lista deduplicada (case-insensitive) para o modal:
    1) ContatoCliente ativo com recebe_documentos_fiscais e e-mail válido
    2) Cliente.email_nf (legado), se ainda não listado
    3) Cliente.email (legado), se ainda não listado
    """
    itens: list[dict[str, Any]] = []
    vistos: set[str] = set()

    def _add(*, email: str, nome: str, origem: str, contato_id: int | None, selecionado: bool) -> None:
        email_limpo = (email or '').strip()
        if not email_limpo:
            return
        try:
            validate_email(email_limpo)
        except ValidationError:
            return
        chave = email_limpo.casefold()
        if chave in vistos:
            return
        vistos.add(chave)
        itens.append(
            {
                'email': email_limpo,
                'nome': (nome or '').strip(),
                'origem': origem,
                'contato_id': contato_id,
                'selecionado': selecionado,
            }
        )

    cliente = _carregar_cliente_nfe(nf)
    if cliente is None:
        return itens

    contatos = getattr(cliente, 'contatos', None)
    if contatos is not None:
        qs = contatos.all() if hasattr(contatos, 'all') else contatos
        for contato in qs:
            if not getattr(contato, 'ativo', True):
                continue
            if not getattr(contato, 'recebe_documentos_fiscais', False):
                continue
            _add(
                email=getattr(contato, 'email', '') or '',
                nome=getattr(contato, 'nome', '') or '',
                origem='contato',
                contato_id=getattr(contato, 'pk', None),
                selecionado=True,
            )

    _add(
        email=getattr(cliente, 'email_nf', '') or '',
        nome='E-mail NF (legado)',
        origem='email_nf',
        contato_id=None,
        selecionado=True,
    )
    _add(
        email=getattr(cliente, 'email', '') or '',
        nome='E-mail principal (legado)',
        origem='email',
        contato_id=None,
        selecionado=True,
    )
    return itens


def resolver_email_destinatario_sugerido(nf: NFeSaida) -> str:
    sugeridos = montar_destinatarios_sugeridos(nf)
    if sugeridos:
        return str(sugeridos[0].get('email') or '').strip()
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

    destinatarios_sugeridos = montar_destinatarios_sugeridos(nf)
    legado = resolver_destinatario_email_cliente_nfe(nf)
    destinatario_sugerido = (
        str(destinatarios_sugeridos[0]['email'])
        if destinatarios_sugeridos
        else str(legado.get('destinatario_sugerido') or '')
    )
    cliente_sem_email = len(destinatarios_sugeridos) == 0
    aviso_sem_email = ''
    if cliente_sem_email and nf.cliente_id:
        aviso_sem_email = (
            'Cliente sem destinatários fiscais cadastrados. '
            'Selecione ou informe o destinatário manualmente.'
        )

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
        'destinatario_sugerido': destinatario_sugerido,
        'destinatarios_sugeridos': destinatarios_sugeridos,
        'cliente_sem_email': cliente_sem_email,
        'destinatario_origem': (
            destinatarios_sugeridos[0]['origem']
            if destinatarios_sugeridos
            else legado.get('destinatario_origem') or ''
        ),
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


def _mensagem_resultado_envio(*, total: int, sucesso: int, erro: int) -> str:
    if total == 0:
        return 'Informe ao menos um destinatário válido.'
    if sucesso == total:
        if total == 1:
            return 'E-mail enviado com sucesso.'
        return f'E-mails enviados com sucesso para {sucesso} destinatários.'
    if sucesso == 0:
        return MSG_SMTP_FALHA if erro else 'Não foi possível enviar o e-mail para nenhum destinatário.'
    return f'Envio parcial: {sucesso} sucesso(s), {erro} falha(s) de {total} destinatário(s).'


def _chave_conjunto_emails(emails: list[str]) -> frozenset[str]:
    return frozenset(e.casefold() for e in emails)


def resolver_lista_destinatarios_envio(*, para: str = '', destinatarios: Any = None) -> list[str]:
    """
    Contrato:
    - destinatarios ausente + para → legado
    - destinatarios presente + para vazio → novo
    - ambos preenchidos → mesmo conjunto (CI) ou 400
    """
    para_bruto = (para or '').strip()
    tem_para = bool(para_bruto)
    tem_destinatarios = destinatarios is not None

    lista_para = normalizar_lista_emails(para_bruto) if tem_para else []
    lista_dest = normalizar_lista_emails_de_payload(destinatarios) if tem_destinatarios else []

    if tem_destinatarios and tem_para:
        if _chave_conjunto_emails(lista_dest) != _chave_conjunto_emails(lista_para):
            raise NFeEnvioEmailError(MSG_CONFLITO_DESTINATARIOS)
        return lista_dest or lista_para
    if tem_destinatarios:
        return lista_dest
    return lista_para


def enviar_email_danfe_xml_nfe_saida(
    nf: NFeSaida,
    *,
    usuario,
    para: str = '',
    cc: str = '',
    assunto: str,
    mensagem: str,
    confirmar_envio: bool = False,
    destinatarios: Any = None,
) -> dict[str, Any]:
    """
    Envia DANFE+XML com privacidade: um EmailMessage por destinatário (TO único).

    CC legado só é permitido com exatamente um destinatário.
    Não existe idempotência server-side; cada POST confirmado é uma nova tentativa.
    """
    pode, motivo = avaliar_envio_email_danfe_xml(nf)
    if not pode:
        raise NFeEnvioEmailError(motivo)

    if not confirmar_envio:
        raise NFeEnvioEmailError('Confirme o envio antes de transmitir o e-mail.')

    lista_destinatarios = resolver_lista_destinatarios_envio(para=para, destinatarios=destinatarios)
    if not lista_destinatarios:
        raise NFeEnvioEmailError('Informe ao menos um destinatário válido.')

    cc_bruto = (cc or '').strip()
    copias_lista = normalizar_lista_emails(cc_bruto) if cc_bruto else []
    if len(lista_destinatarios) > 1 and copias_lista:
        raise NFeEnvioEmailError(MSG_CC_MULTI)
    if len(lista_destinatarios) != 1:
        copias_lista = []

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

    # Anexos gerados/carregados uma única vez por requisição e reutilizados.
    xml_texto = resolver_xml_autorizado_danfe(nf)
    try:
        pdf_bytes, _meta = gerar_danfe_autorizado_nfe_saida(nf)
    except Exception as exc:
        raise NFeEnvioEmailError('Não foi possível gerar o DANFE PDF para anexo.') from exc
    if not pdf_bytes:
        raise NFeEnvioEmailError('Não foi possível gerar o DANFE PDF para anexo.')
    nome_xml = nome_arquivo_xml_autorizado(nf)
    nome_pdf = nome_arquivo_danfe_autorizado(nf)

    from_email = (
        getattr(settings, 'NEXUS_EMAIL_OPERACIONAL', None) or settings.DEFAULT_FROM_EMAIL or ''
    ).strip()
    if not from_email:
        raise NFeEnvioEmailError('E-mail remetente operacional não configurado no ambiente.')

    copias_str = ', '.join(copias_lista)
    resultados: list[dict[str, Any]] = []
    registros: list[NFeSaidaEnvioEmail] = []
    sucesso_count = 0
    erro_count = 0

    for email_dest in lista_destinatarios:
        msg_kwargs: dict[str, Any] = {
            'subject': assunto_limpo,
            'body': mensagem_limpa,
            'from_email': from_email,
            'to': [email_dest],
        }
        if copias_lista:
            msg_kwargs['cc'] = list(copias_lista)
        email = EmailMessage(**msg_kwargs)
        email.attach(nome_xml, xml_texto.encode('utf-8'), 'application/xml')
        email.attach(nome_pdf, pdf_bytes, 'application/pdf')

        try:
            email.send(fail_silently=False)
        except (smtplib.SMTPException, OSError, ConnectionError) as exc:
            logger.warning(
                'Falha SMTP envio DANFE/XML NF-e id=%s destinatario=%s tipo=%s',
                nf.pk,
                email_dest,
                type(exc).__name__,
            )
            registro = _registrar_log_envio(
                nf=nf,
                usuario=usuario,
                destinatario=email_dest,
                copias=copias_str,
                assunto=assunto_limpo,
                ambiente=ambiente,
                status_envio=NFeSaidaEnvioEmail.StatusEnvio.ERRO,
                mensagem_erro=MSG_SMTP_FALHA,
                anexo_xml=True,
                anexo_danfe_pdf=True,
            )
            erro_count += 1
            registros.append(registro)
            resultados.append(
                {
                    'email': email_dest,
                    'status': NFeSaidaEnvioEmail.StatusEnvio.ERRO,
                    'mensagem': MSG_SMTP_FALHA,
                    # aliases de compatibilidade
                    'status_envio': NFeSaidaEnvioEmail.StatusEnvio.ERRO,
                    'mensagem_erro': MSG_SMTP_FALHA,
                    'envio_id': registro.pk,
                }
            )
            continue

        registro = _registrar_log_envio(
            nf=nf,
            usuario=usuario,
            destinatario=email_dest,
            copias=copias_str,
            assunto=assunto_limpo,
            ambiente=ambiente,
            status_envio=NFeSaidaEnvioEmail.StatusEnvio.SUCESSO,
            anexo_xml=True,
            anexo_danfe_pdf=True,
        )
        sucesso_count += 1
        registros.append(registro)
        resultados.append(
            {
                'email': email_dest,
                'status': NFeSaidaEnvioEmail.StatusEnvio.SUCESSO,
                'mensagem': 'E-mail enviado com sucesso.',
                'status_envio': NFeSaidaEnvioEmail.StatusEnvio.SUCESSO,
                'mensagem_erro': '',
                'envio_id': registro.pk,
            }
        )
        logger.info(
            'Envio DANFE/XML NF-e id=%s usuario=%s destinatario=%s ambiente=%s',
            nf.pk,
            getattr(usuario, 'pk', None),
            email_dest,
            ambiente,
        )

    total = len(lista_destinatarios)
    if sucesso_count == total:
        status_geral = 'SUCESSO'
    elif sucesso_count > 0:
        status_geral = 'PARCIAL'
    else:
        status_geral = 'ERRO'

    mensagem_resultado = _mensagem_resultado_envio(
        total=total,
        sucesso=sucesso_count,
        erro=erro_count,
    )
    ultimo_registro = next(
        (
            r
            for r in reversed(registros)
            if r.status_envio == NFeSaidaEnvioEmail.StatusEnvio.SUCESSO
        ),
        registros[-1] if registros else None,
    )

    return {
        'ok': status_geral in ('SUCESSO', 'PARCIAL'),
        'status_geral': status_geral,
        'mensagem': mensagem_resultado,
        'total': total,
        'sucessos': sucesso_count,
        'falhas': erro_count,
        # aliases legados
        'sucesso': sucesso_count,
        'erro': erro_count,
        'resultados': resultados,
        'envio': _serializar_ultimo_envio(ultimo_registro),
        'envios': [_serializar_ultimo_envio(r) for r in registros],
    }
