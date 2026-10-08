"""Critérios para identificar dados artificiais gerados por Cursor/testes."""

from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.models import NFeSaida
from apps.produtos.models import Produto

EMPRESAS_PRESERVAR_RAZAO = (
    'NEXUS VALVULAS E CONEXOES INDUSTRIAIS LTDA',
)

CLIENTES_PRESERVAR_RAZAO = (
    'DYNATECH INDUSTRIAS QUIMICAS LTDA',
    'CLIENTE REVISAO PDF CQ LTDA',
)

RE_PV_VALIDO = re.compile(r'^PV-\d{8}-\d+$', re.I)
RE_PV_HASH = re.compile(r'^PV-[a-f0-9]{4,12}$', re.I)
RE_RAZAO_EMIT_TESTE = re.compile(r'^Emit(?:ente\s+\d+)?$', re.I)
RE_RAZAO_CLI_TESTE = re.compile(r'^Cli(?:ente\s+\d+)?$', re.I)


def _norm(s: str | None) -> str:
    return (s or '').strip()


def _razao_preservada(razao: str, lista: tuple[str, ...]) -> bool:
    r = _norm(razao).upper()
    return any(p in r for p in lista)


def nfe_deve_preservar(nf: NFeSaida) -> tuple[bool, str]:
    if (nf.status_emissao_sefaz or '').strip() == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        return True, 'autorizada_homologacao'
    if (nf.cstat_autorizacao or '').strip() == '100':
        return True, 'cstat_100'
    if (nf.protocolo_autorizacao or '').strip():
        return True, 'protocolo_real'
    if (nf.xml_autorizado or '').strip():
        return True, 'xml_autorizado'
    chave = (nf.chave_acesso or '').strip()
    if len(chave) == 44 and chave.isdigit():
        return True, 'chave_acesso'
    return False, ''


def pedido_deve_preservar(pedido: PedidoVenda) -> tuple[bool, str]:
    if NFeSaida.objects.filter(pedido_venda=pedido).filter(
        Q(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO)
        | Q(cstat_autorizacao='100')
        | ~Q(protocolo_autorizacao='')
        | ~Q(xml_autorizado=''),
    ).exists():
        return True, 'nfe_autorizada_vinculada'
    if FaturamentoPedidoVenda.objects.filter(
        pedido=pedido,
        nfe_saida__isnull=False,
    ).filter(
        Q(nfe_saida__status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO)
        | Q(nfe_saida__cstat_autorizacao='100'),
    ).exists():
        return True, 'faturamento_nfe_autorizada'
    numero = _norm(pedido.numero)
    if RE_PV_VALIDO.match(numero):
        return True, 'pv_padrao_valido'
    return False, ''


def cliente_deve_preservar(cliente: Cliente) -> tuple[bool, str]:
    if _razao_preservada(cliente.razao_social, CLIENTES_PRESERVAR_RAZAO):
        return True, 'cliente_real'
    if NFeSaida.objects.filter(cliente=cliente).filter(
        Q(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO)
        | Q(cstat_autorizacao='100')
        | ~Q(protocolo_autorizacao='')
        | ~Q(xml_autorizado=''),
    ).exists():
        return True, 'nfe_autorizada_vinculada'
    if PedidoVenda.objects.filter(cliente=cliente).filter(
        numero__regex=r'^PV-\d{8}-\d+$',
    ).exists():
        return True, 'pv_real_vinculado'
    return False, ''


def empresa_deve_preservar(empresa: Empresa) -> tuple[bool, str]:
    if _razao_preservada(empresa.razao_social, EMPRESAS_PRESERVAR_RAZAO):
        return True, 'empresa_real'
    if empresa.certificado_arquivo:
        return True, 'certificado_digital'
    if PedidoVenda.objects.filter(empresa_emitente=empresa).filter(
        nf_saidas__status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
    ).exists():
        return True, 'nfe_autorizada_vinculada'
    if PedidoVenda.objects.filter(empresa_emitente=empresa, numero__regex=r'^PV-\d{8}-\d+$').exists():
        return True, 'pv_real_vinculado'
    return False, ''


def avaliar_empresa(empresa: Empresa) -> dict[str, Any]:
    preservar, motivo_pres = empresa_deve_preservar(empresa)
    if preservar:
        return {'id': empresa.pk, 'candidato': False, 'motivo': motivo_pres, 'razao_social': empresa.razao_social}

    motivos: list[str] = []
    razao = _norm(empresa.razao_social)
    if RE_RAZAO_EMIT_TESTE.match(razao) or razao == 'Emit':
        motivos.append('razao_emit_teste')
    cidade = _norm(empresa.cidade)
    if cidade.startswith('/') or cidade == '/SP':
        motivos.append('cidade_incompleta')
    if not empresa.certificado_arquivo:
        motivos.append('sem_certificado')
    if not _norm(empresa.nome_fantasia) and len(razao) <= 20:
        motivos.append('nome_generico')

    return {
        'id': empresa.pk,
        'candidato': bool(motivos),
        'motivos': motivos,
        'razao_social': empresa.razao_social,
        'cnpj': empresa.cnpj,
        'cidade': empresa.cidade,
        'uf': empresa.uf,
    }


def avaliar_cliente(cliente: Cliente) -> dict[str, Any]:
    preservar, motivo_pres = cliente_deve_preservar(cliente)
    if preservar:
        return {'id': cliente.pk, 'candidato': False, 'motivo': motivo_pres, 'razao_social': cliente.razao_social}

    motivos: list[str] = []
    razao = _norm(cliente.razao_social)
    if RE_RAZAO_CLI_TESTE.match(razao) or razao == 'Cli':
        motivos.append('razao_cli_teste')
    if not _norm(cliente.telefone) and not _norm(cliente.email):
        motivos.append('contato_incompleto')
    if not _norm(cliente.cidade) or not _norm(cliente.logradouro):
        motivos.append('endereco_incompleto')

    return {
        'id': cliente.pk,
        'candidato': bool(motivos),
        'motivos': motivos,
        'razao_social': cliente.razao_social,
        'cnpj': cliente.cnpj,
    }


def avaliar_pedido(pedido: PedidoVenda) -> dict[str, Any]:
    preservar, motivo_pres = pedido_deve_preservar(pedido)
    if preservar:
        return {'id': pedido.pk, 'candidato': False, 'motivo': motivo_pres, 'numero': pedido.numero}

    numero = _norm(pedido.numero)
    motivos: list[str] = []
    if not RE_PV_VALIDO.match(numero):
        if numero.upper().startswith('PV-'):
            motivos.append('numero_fora_padrao')
            if RE_PV_HASH.match(numero):
                motivos.append('pv_hash_cursor')
    if RE_RAZAO_CLI_TESTE.match(_norm(getattr(pedido.cliente, 'razao_social', ''))):
        motivos.append('cliente_artificial')

    return {
        'id': pedido.pk,
        'candidato': bool(motivos),
        'motivos': motivos,
        'numero': pedido.numero,
        'cliente_id': pedido.cliente_id,
        'status': pedido.status,
    }


def avaliar_nfe(nf: NFeSaida) -> dict[str, Any]:
    preservar, motivo_pres = nfe_deve_preservar(nf)
    if preservar:
        return {
            'id': nf.pk,
            'candidato': False,
            'motivo': motivo_pres,
            'numero': nf.numero,
            'status': nf.status,
            'status_emissao_sefaz': nf.status_emissao_sefaz,
        }

    motivos: list[str] = []
    st = (nf.status or '').upper()
    if st in ('RASCUNHO', 'CANCELADA_INTERNA', 'CANCELADA', 'CANCELADO'):
        motivos.append(f'status_{st.lower()}')
    if not (nf.protocolo_autorizacao or '').strip():
        motivos.append('sem_protocolo')
    if not (nf.xml_autorizado or '').strip():
        motivos.append('sem_xml_autorizado')

    pedido = nf.pedido_venda
    if pedido and not RE_PV_VALIDO.match(_norm(pedido.numero)):
        motivos.append('pv_artificial')
    cliente = nf.cliente
    if cliente and RE_RAZAO_CLI_TESTE.match(_norm(cliente.razao_social)):
        motivos.append('cliente_artificial')

    return {
        'id': nf.pk,
        'candidato': bool(motivos),
        'motivos': motivos,
        'numero': nf.numero,
        'status': nf.status,
        'cliente_id': nf.cliente_id,
        'pedido_venda_id': nf.pedido_venda_id,
    }


def avaliar_faturamento(fat: FaturamentoPedidoVenda) -> dict[str, Any]:
    nf = fat.nfe_saida
    if nf:
        pres, motivo = nfe_deve_preservar(nf)
        if pres:
            return {
                'id': fat.pk,
                'candidato': False,
                'motivo': motivo,
                'numero_faturamento': fat.numero_faturamento,
            }

    motivos: list[str] = []
    pedido = fat.pedido
    if pedido and not RE_PV_VALIDO.match(_norm(pedido.numero)):
        motivos.append('pv_artificial')
    if pedido and RE_RAZAO_CLI_TESTE.match(_norm(getattr(pedido.cliente, 'razao_social', ''))):
        motivos.append('cliente_artificial')
    if not nf and fat.status in (FaturamentoPedidoVenda.Status.RASCUNHO, FaturamentoPedidoVenda.Status.CANCELADO):
        motivos.append('sem_nfe_operacional')

    return {
        'id': fat.pk,
        'candidato': bool(motivos),
        'motivos': motivos,
        'numero_faturamento': fat.numero_faturamento,
        'pedido_id': fat.pedido_id,
        'status': fat.status,
    }


RE_PROD_TESTE = re.compile(r'^(PROD\s*NF|PROD\s*FAT|PROD)$', re.I)


def avaliar_produto(produto: Produto) -> dict[str, Any]:
    """Identifica produto candidato à limpeza (conservador)."""
    classificacao = classificar_produto(produto)
    if classificacao['classificacao'] == 'provavelmente_real':
        return {
            'id': produto.pk,
            'candidato': False,
            'motivo': 'produto_real_ou_vinculado',
            'descricao': classificacao['descricao'],
            'codigo': classificacao['codigo'],
        }

    desc = _norm(produto.descricao)
    codigo = _norm(getattr(produto, 'codigo_completo', '') or '')
    motivos: list[str] = list(classificacao.get('motivos') or [])

    if RE_PROD_TESTE.match(desc):
        motivos.append('descricao_teste')
    if re.search(r'NF402|FAT-PROD|test|cursor|mock', codigo, re.I):
        motivos.append('codigo_teste')
    if re.search(r'teste|cursor|mock', desc, re.I):
        motivos.append('descricao_teste')

    # Ausência de material sozinha não classifica como teste
    candidato = bool(motivos) and classificacao['classificacao'] == 'suspeito'

    return {
        'id': produto.pk,
        'candidato': candidato,
        'motivos': motivos,
        'descricao': desc,
        'codigo': codigo,
        'classificacao': classificacao['classificacao'],
    }


def classificar_produto(produto: Produto) -> dict[str, Any]:
    usado_nfe = ItemPedidoVenda.objects.filter(produto=produto).exists()
    usado_pedido_real = ItemPedidoVenda.objects.filter(
        produto=produto,
        pedido__numero__regex=r'^PV-\d{8}-\d+$',
    ).exists()
    usado_nfe_real = NFeSaida.objects.filter(
        itens__produto=produto,
    ).filter(
        Q(status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO)
        | Q(cstat_autorizacao='100'),
    ).exists()

    desc = _norm(produto.descricao)
    ncm = _norm(produto.get_ncm_efetivo_codigo() if hasattr(produto, 'get_ncm_efetivo_codigo') else (produto.ncm or ''))
    codigo = _norm(getattr(produto, 'codigo_completo', '') or '')

    classificacao = 'revisar'
    motivos: list[str] = []

    if usado_nfe_real or usado_pedido_real:
        classificacao = 'provavelmente_real'
        motivos.append('usado_documento_real')
    elif usado_nfe:
        motivos.append('usado_pedido_teste')

    if not ncm:
        motivos.append('ncm_vazio')
        if classificacao != 'provavelmente_real':
            classificacao = 'suspeito'
    if len(desc) < 4 or desc.lower() in ('prod', 'produto', 'prod nf', 'prod fat'):
        motivos.append('descricao_generica')
        if classificacao != 'provavelmente_real':
            classificacao = 'suspeito'
    if re.search(r'NF402|FAT-PROD|test', codigo, re.I):
        motivos.append('codigo_teste')
        classificacao = 'suspeito'

    return {
        'id': produto.pk,
        'candidato_exclusao': False,
        'classificacao': classificacao,
        'motivos': motivos,
        'descricao': desc,
        'codigo': codigo,
        'ncm': ncm,
        'acao_recomendada': 'revisar_manualmente',
    }
