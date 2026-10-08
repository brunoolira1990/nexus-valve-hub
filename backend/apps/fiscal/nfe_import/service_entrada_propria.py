"""ERP 4.0.14.x — importação de NF-e de entrada própria já emitida (operacional)."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import (
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)

from ..nfe_historica_classificacao import (
    ACAO_IMPORTAR_ENTRADA_PROPRIA_EMITIDA,
    MSG_ENTRADA_PROPRIA_JA_EMITIDA,
    eh_entrada_propria_ja_emitida,
    resolve_cliente_from_party,
)
from .falha_xml import falha_com_traceback, montar_falha_importacao_xml
from .parser_entrada import parse_nfe_entrada_xml


def _xml_texto(conteudo: bytes) -> str:
    try:
        return conteudo.decode('utf-8')
    except UnicodeDecodeError:
        return conteudo.decode('latin-1', errors='replace')


def _checar_duplicidade(chave: str) -> str | None:
    if NFeEntrada.objects.filter(chave_acesso=chave).exists():
        return 'Esta chave já consta em NF-e Entrada operacional.'
    if NFeEntradaHistoricaImportada.objects.filter(chave_acesso=chave).exists():
        return 'Esta chave já consta na Base NF-e Entrada Importada (fornecedor).'
    if NFeSaidaHistoricaImportada.objects.filter(chave_acesso=chave).exists():
        return 'Esta chave já consta na Base NF-e Saída Importada.'
    return None


def importar_arquivos_entrada_propria_emitida(arquivos: list[tuple[str, bytes]]) -> dict[str, Any]:
    importadas: list[dict[str, Any]] = []
    duplicadas: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []

    for nome, conteudo in arquivos:
        nome = nome or 'sem_nome.xml'
        parsed = parse_nfe_entrada_xml(conteudo)
        if parsed.erro:
            ch = (parsed.chave_acesso or '').strip()
            te = (
                'Leitura XML'
                if ('XML inválido' in parsed.erro or 'corrompido' in parsed.erro)
                else 'Validação da NF-e / evento'
            )
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=ch,
                    tipo_documento='NFE' if ch else 'DESCONHECIDO',
                    tipo_erro=te,
                    mensagem_completa=parsed.erro,
                    acao_sugerida=(
                        'Verifique se o XML é NF-e de entrada própria (tpNF=0) com infNFe completo e chave válida (44 dígitos).'
                    ),
                )
            )
            continue

        is_propria, empresa = eh_entrada_propria_ja_emitida(
            parsed.emit_json,
            parsed.dest_json,
            tp_nf=parsed.tp_nf,
        )
        if not is_propria or not empresa:
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=(
                        'O XML não foi reconhecido como NF-e de entrada própria já emitida pela Empresa '
                        '(emitente = Empresa cadastrada e tpNF=0).'
                    ),
                    acao_sugerida=(
                        'Para compras de fornecedor use Base NF-e Entrada Importada. '
                        'Para vendas históricas use Base NF-e Saída Importada. '
                        f'{ACAO_IMPORTAR_ENTRADA_PROPRIA_EMITIDA}'
                    ),
                )
            )
            continue

        dup_msg = _checar_duplicidade(parsed.chave_acesso)
        if dup_msg:
            duplicadas.append(
                {
                    'arquivo': nome,
                    'chave_acesso': parsed.chave_acesso,
                    'mensagem': dup_msg,
                }
            )
            continue

        try:
            with transaction.atomic():
                dh = parsed.dh_emissao
                data_doc = dh.date() if dh is not None else timezone.localdate()
                cliente = resolve_cliente_from_party(parsed.dest_json)
                nf = NFeEntrada.objects.create(
                    numero=parsed.numero[:64],
                    serie=(parsed.serie or '')[:4],
                    chave_acesso=parsed.chave_acesso,
                    fornecedor=None,
                    empresa_emitente=empresa,
                    cliente_destinatario=cliente,
                    data=data_doc,
                    valor_total=parsed.valor_total_nf,
                    tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_IMPORTADA,
                    status_operacional=NFeEntrada.StatusOperacional.IMPORTADA_PENDENTE_CONFERENCIA,
                    emit_json=parsed.emit_json,
                    dest_json=parsed.dest_json,
                    itens_json=parsed.itens,
                    xml_importado=_xml_texto(conteudo),
                    nome_arquivo=nome[:255],
                    importado_em=timezone.now(),
                )
        except Exception as e:
            erros.append(
                falha_com_traceback(
                    arquivo=nome,
                    chave=parsed.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Gravação no banco',
                    mensagem_completa=f'Falha ao gravar NF-e de entrada própria: {e}',
                    acao_sugerida='Verifique logs, duplicidade de chave e integridade do XML.',
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
                'tipo_origem': nf.tipo_origem,
                'status_operacional': nf.status_operacional,
            }
        )

    return {
        'importadas': importadas,
        'duplicadas': duplicadas,
        'erros': erros,
        'resumo': {
            'total_arquivos': len(arquivos),
            'importadas': len(importadas),
            'duplicadas': len(duplicadas),
            'erros': len(erros),
        },
    }


def mensagem_rejeicao_entrada_propria_em_outro_fluxo() -> tuple[str, str]:
    return MSG_ENTRADA_PROPRIA_JA_EMITIDA, ACAO_IMPORTAR_ENTRADA_PROPRIA_EMITIDA
