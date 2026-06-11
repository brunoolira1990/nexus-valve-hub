from __future__ import annotations

import xml.etree.ElementTree as ET

from django.db import transaction

from ..models import ItemNFeEntradaHistoricaImportada, NFeEntradaHistoricaImportada, NFeSaidaHistoricaImportada
from ..nfe_historica_classificacao import (
    classificar_por_empresa,
    eh_entrada_propria_ja_emitida,
    norm_digits,
    reclassificar_saida_para_entrada,
    resolve_fornecedor_from_party,
)
from .service_entrada_propria import mensagem_rejeicao_entrada_propria_em_outro_fluxo
from ..services.reforma_tributaria import enriquecer_reforma_e_outros_json_nf
from .falha_xml import falha_com_traceback, montar_falha_importacao_xml
from .parser_entrada import parse_nfe_entrada_xml


def _norm_digits(val: str) -> str:
    return norm_digits(val)


def importar_arquivos_entrada(arquivos: list[tuple[str, bytes]]) -> dict[str, Any]:
    importadas: list[dict[str, Any]] = []
    duplicadas: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []

    for nome, conteudo in arquivos:
        nome = nome or 'sem_nome.xml'
        try:
            root = ET.fromstring(conteudo)
            local = root.tag.split('}')[-1] if '}' in root.tag else root.tag
            if local in {'procEventoNFe', 'evento'}:
                erros.append(
                    montar_falha_importacao_xml(
                        arquivo=nome,
                        chave='',
                        tipo_documento='EVENTO',
                        tipo_erro='Validação da NF-e / evento',
                        mensagem_completa=(
                            'XML de evento detectado (ex.: cancelamento 110111). '
                            'Eventos não devem ser importados como XML principal de NF-e de entrada.'
                        ),
                        acao_sugerida=(
                            'Use o importador de NF-e de saída histórica para eventos de cancelamento vinculados à nota. '
                            'Aqui aceite apenas XML de NF-e com infNFe (compra).'
                        ),
                    )
                )
                continue
        except ET.ParseError:
            pass
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
                        'Verifique se o XML é NF-e de entrada (tpNF=0) com infNFe completo e chave válida (44 dígitos). '
                        'Arquivos corrompidos ou HTML da consulta pública não são aceitos.'
                    ),
                )
            )
            continue

        if NFeEntradaHistoricaImportada.objects.filter(chave_acesso=parsed.chave_acesso).exists():
            duplicadas.append({'arquivo': nome, 'chave_acesso': parsed.chave_acesso, 'mensagem': 'Esta chave de NF-e já foi importada.'})
            continue

        classificacao = classificar_por_empresa(parsed.emit_json, parsed.dest_json)
        is_propria, _emp = eh_entrada_propria_ja_emitida(
            parsed.emit_json,
            parsed.dest_json,
            tp_nf=parsed.tp_nf,
        )
        if is_propria:
            msg, acao = mensagem_rejeicao_entrada_propria_em_outro_fluxo()
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=msg,
                    acao_sugerida=acao,
                )
            )
            continue
        if classificacao.tipo_fluxo == 'saida' and classificacao.empresa_emitente:
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=(
                        'Emitente do XML corresponde à Empresa cadastrada (emissão própria de saída/venda). '
                        'Para faturamento/vendas use o importador de NF-e de saída histórica.'
                    ),
                    acao_sugerida=(
                        'Importe notas de venda em "NF-e Saída Histórica/XML". Esta tela é apenas para compras (destinatário = Empresa).'
                    ),
                )
            )
            continue
        if classificacao.tipo_fluxo != 'entrada' or not classificacao.empresa_destinataria:
            erros.append(
                montar_falha_importacao_xml(
                    arquivo=nome,
                    chave=parsed.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Classificação / cadastro',
                    mensagem_completa=(
                        'Classificação bloqueada: não foi possível identificar a Empresa cadastrada por CNPJ '
                        'como destinatária da NF-e.'
                    ),
                    acao_sugerida=(
                        'Cadastre a Empresa com o mesmo CNPJ do destinatário no XML ou corrija o XML importado.'
                    ),
                )
            )
            continue

        registro_saida = NFeSaidaHistoricaImportada.objects.filter(chave_acesso=parsed.chave_acesso).first()
        if registro_saida:
            resultado = reclassificar_saida_para_entrada(registro_saida)
            if resultado in {'reclassificada', 'removida_saida_duplicada_entrada'}:
                if NFeEntradaHistoricaImportada.objects.filter(chave_acesso=parsed.chave_acesso).exists():
                    duplicadas.append(
                        {
                            'arquivo': nome,
                            'chave_acesso': parsed.chave_acesso,
                            'mensagem': 'NF-e reclassificada automaticamente de saída para entrada histórica.',
                        }
                    )
                    continue
            else:
                erros.append(
                    montar_falha_importacao_xml(
                        arquivo=nome,
                        chave=parsed.chave_acesso,
                        tipo_documento='NFE',
                        tipo_erro='Classificação / cadastro',
                        mensagem_completa=(
                            'Esta chave já consta em NF-e de saída histórica e não atende os critérios '
                            'de reclassificação automática para entrada.'
                        ),
                        acao_sugerida=(
                            'Ajuste o cadastro ou remova a nota de saída histórica conflitante se for o caso de reclassificação manual. '
                            'Consulte o suporte se a nota for compra e estiver apenas em saída por engano.'
                        ),
                    )
                )
                continue

        try:
            with transaction.atomic():
                fornecedor = resolve_fornecedor_from_party(parsed.emit_json)
                papel = 'destinatario'

                nf = NFeEntradaHistoricaImportada.objects.create(
                    chave_acesso=parsed.chave_acesso,
                    numero=parsed.numero[:16],
                    serie=parsed.serie[:4],
                    modelo=parsed.modelo[:4],
                    dh_emissao=parsed.dh_emissao,
                    tp_amb=parsed.tp_amb[:1],
                    tp_nf=parsed.tp_nf[:1],
                    nat_op=parsed.nat_op[:120],
                    versao_layout=parsed.versao_layout[:16],
                    cstat=parsed.cstat[:8],
                    xmotivo=parsed.xmotivo[:255],
                    protocolo=parsed.protocolo[:30],
                    valor_produtos=parsed.valor_produtos,
                    valor_total_nf=parsed.valor_total_nf,
                    v_frete=parsed.v_frete,
                    v_seg=parsed.v_seg,
                    v_desc=parsed.v_desc,
                    v_outro=parsed.v_outro,
                    emit_json=parsed.emit_json,
                    dest_json=parsed.dest_json,
                    totais_json=parsed.totais_json,
                    reforma_e_outros_json=enriquecer_reforma_e_outros_json_nf(parsed.totais_json, parsed.reforma_e_outros_json),
                    prot_json=parsed.prot_json,
                    empresa_destinataria=classificacao.empresa_destinataria,
                    fornecedor_emitente=fornecedor,
                    papel_empresa_no_documento=papel,
                    nome_arquivo=nome[:255],
                )
                ItemNFeEntradaHistoricaImportada.objects.bulk_create(
                    [
                        ItemNFeEntradaHistoricaImportada(
                            nf=nf,
                            n_item=it['n_item'],
                            prod_json=it.get('prod') or {},
                            imposto_json=it.get('imposto') or {},
                        )
                        for it in parsed.itens
                    ]
                )
        except Exception as e:
            erros.append(
                falha_com_traceback(
                    arquivo=nome,
                    chave=parsed.chave_acesso,
                    tipo_documento='NFE',
                    tipo_erro='Gravação no banco',
                    mensagem_completa=f'Falha ao gravar a NF-e de entrada: {e}',
                    acao_sugerida=(
                        'Verifique logs do servidor e duplicidade de chave. Copie o diagnóstico completo para análise.'
                    ),
                    exc=e,
                )
            )
            continue

        importadas.append({'arquivo': nome, 'id': nf.id, 'chave_acesso': nf.chave_acesso, 'numero': nf.numero, 'serie': nf.serie})

    return {
        'importadas': importadas,
        'duplicadas': duplicadas,
        'erros': erros,
        'resumo': {'total_arquivos': len(arquivos), 'importadas': len(importadas), 'duplicadas': len(duplicadas), 'erros': len(erros)},
    }

