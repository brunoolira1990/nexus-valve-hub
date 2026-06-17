"""Parser do retorno SEFAZ NFeConsultaCadastro (retConsCad)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from apps.fiscal.nfe_integracao.adapters.status_servico_parser import normalizar_xml_bruto

logger = logging.getLogger(__name__)

CSTAT_CADASTRO_ENCONTRADO = frozenset({'111', '112'})

SITUACAO_IE_POR_CSIT = {
    '0': 'Não habilitado',
    '1': 'Habilitado',
}


@dataclass
class InscricaoEstadualCadastro:
    inscricao_estadual: str
    situacao_ie: str
    situacao_codigo: str
    uf: str
    cnpj: str
    razao_social: str
    municipio: str
    cnae: str
    habilitada: bool


@dataclass
class ResultadoConsultaCadastro:
    sucesso: bool
    cnpj: str
    uf: str
    c_stat: str
    x_motivo: str
    inscricoes_estaduais: list[InscricaoEstadualCadastro] = field(default_factory=list)
    inscricao_estadual: str = ''
    situacao_ie: str = ''
    razao_social: str = ''
    municipio: str = ''
    cnae: str = ''
    mensagem_usuario: str = ''
    erro_codigo: str = ''
    xml_resposta: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'sucesso': self.sucesso,
            'cnpj': self.cnpj,
            'uf': self.uf,
            'inscricao_estadual': self.inscricao_estadual,
            'inscricoes_estaduais': [
                {
                    'inscricao_estadual': item.inscricao_estadual,
                    'situacao_ie': item.situacao_ie,
                    'situacao_codigo': item.situacao_codigo,
                    'uf': item.uf,
                    'cnpj': item.cnpj,
                    'razao_social': item.razao_social,
                    'municipio': item.municipio,
                    'cnae': item.cnae,
                    'habilitada': item.habilitada,
                }
                for item in self.inscricoes_estaduais
            ],
            'situacao_ie': self.situacao_ie,
            'razao_social': self.razao_social,
            'municipio': self.municipio,
            'cnae': self.cnae,
            'fonte': 'SEFAZ_NFE_CONSULTA_CADASTRO',
            'mensagem_usuario': self.mensagem_usuario,
            'erro_codigo': self.erro_codigo,
            'c_stat': self.c_stat,
            'x_motivo': self.x_motivo,
        }


def _xpath_local(node: etree._Element | None, tag: str, *, descendants: bool = False) -> list[etree._Element]:
    if node is None:
        return []
    axis = './/' if descendants else ''
    return node.xpath(f'{axis}*[local-name()="{tag}"]')


def _primeiro_local(node: etree._Element | None, tag: str, *, descendants: bool = False) -> etree._Element | None:
    nodes = _xpath_local(node, tag, descendants=descendants)
    return nodes[0] if nodes else None


def _texto(node: etree._Element | None, tag: str) -> str:
    if node is None:
        return ''
    el = _primeiro_local(node, tag, descendants=False)
    if el is None:
        el = _primeiro_local(node, tag, descendants=True)
    return (el.text or '').strip() if el is not None else ''


def _parse_inf_cad(node: etree._Element) -> InscricaoEstadualCadastro | None:
    ie = _texto(node, 'IE')
    if not ie:
        return None
    c_sit = _texto(node, 'cSit')
    situacao = SITUACAO_IE_POR_CSIT.get(c_sit, c_sit or 'Desconhecida')
    habilitada = c_sit == '1'
    return InscricaoEstadualCadastro(
        inscricao_estadual=ie,
        situacao_ie=situacao,
        situacao_codigo=c_sit,
        uf=_texto(node, 'UF'),
        cnpj=_texto(node, 'CNPJ'),
        razao_social=_texto(node, 'xNome'),
        municipio=_texto(node, 'xMun'),
        cnae=_texto(node, 'CNAE'),
        habilitada=habilitada,
    )


def _listar_inf_cad(ret: etree._Element) -> list[etree._Element]:
    """Localiza infCad como filho direto ou aninhado (varia por UF/versão do WS)."""
    return _xpath_local(ret, 'infCad', descendants=True)


def _localizar_ret_cons_cad(root: etree._Element) -> etree._Element | None:
    if etree.QName(root.tag).localname == 'retConsCad':
        return root
    return _primeiro_local(root, 'retConsCad', descendants=True)


def _priorizar_inscricao(inscricoes: list[InscricaoEstadualCadastro], uf: str) -> InscricaoEstadualCadastro | None:
    if not inscricoes:
        return None
    uf_ref = (uf or '').strip().upper()

    def pontuacao(item: InscricaoEstadualCadastro) -> tuple[int, int]:
        uf_match = 0 if uf_ref and item.uf.upper() == uf_ref else 1
        habilitada = 0 if item.habilitada else 1
        return (habilitada, uf_match)

    return sorted(inscricoes, key=pontuacao)[0]


def parse_consulta_cadastro_response(
    raw: Any,
    *,
    cnpj: str,
    uf: str,
) -> ResultadoConsultaCadastro:
    xml = normalizar_xml_bruto(raw)
    resultado = ResultadoConsultaCadastro(
        sucesso=False,
        cnpj=cnpj,
        uf=uf,
        c_stat='',
        x_motivo='',
        xml_resposta=xml,
    )
    if not xml.strip():
        resultado.mensagem_usuario = 'Consulta SEFAZ indisponível no momento.'
        resultado.erro_codigo = 'RESPOSTA_VAZIA'
        return resultado

    try:
        root = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
    except etree.XMLSyntaxError:
        logger.debug('XML inválido na consulta cadastro SEFAZ')
        resultado.mensagem_usuario = 'Consulta SEFAZ indisponível no momento.'
        resultado.erro_codigo = 'XML_INVALIDO'
        return resultado

    ret = _localizar_ret_cons_cad(root)
    if ret is None:
        resultado.mensagem_usuario = 'Consulta SEFAZ indisponível no momento.'
        resultado.erro_codigo = 'RETORNO_NAO_ENCONTRADO'
        return resultado

    inf_cons = _primeiro_local(ret, 'infCons', descendants=True)
    c_stat = _texto(inf_cons, 'cStat')
    x_motivo = _texto(inf_cons, 'xMotivo')
    resultado.c_stat = c_stat
    resultado.x_motivo = x_motivo

    inscricoes: list[InscricaoEstadualCadastro] = []
    for inf_cad in _listar_inf_cad(ret):
        parsed = _parse_inf_cad(inf_cad)
        if parsed:
            inscricoes.append(parsed)
    resultado.inscricoes_estaduais = inscricoes

    if c_stat in CSTAT_CADASTRO_ENCONTRADO and inscricoes:
        escolhida = _priorizar_inscricao(inscricoes, uf)
        if escolhida:
            resultado.sucesso = True
            resultado.inscricao_estadual = escolhida.inscricao_estadual
            resultado.situacao_ie = escolhida.situacao_ie
            resultado.razao_social = escolhida.razao_social
            resultado.municipio = escolhida.municipio
            resultado.cnae = escolhida.cnae
            if len(inscricoes) > 1:
                resultado.mensagem_usuario = (
                    'Foram encontradas múltiplas inscrições estaduais. Revise e escolha a correta.'
                )
            elif not escolhida.habilitada:
                resultado.mensagem_usuario = (
                    f'Inscrição Estadual encontrada com situação «{escolhida.situacao_ie}». '
                    'Revise antes de aplicar.'
                )
            else:
                resultado.mensagem_usuario = 'Inscrição Estadual encontrada na SEFAZ.'
        return resultado

    if c_stat in CSTAT_CADASTRO_ENCONTRADO and not inscricoes:
        resultado.mensagem_usuario = (
            'A SEFAZ confirmou o cadastro, mas não foi possível interpretar a Inscrição Estadual retornada.'
        )
        resultado.erro_codigo = 'IE_RESPOSTA_NAO_INTERPRETADA'
        return resultado

    if c_stat in {'257', '258', '259', '260', '261', '262'}:
        resultado.mensagem_usuario = 'Nenhuma Inscrição Estadual localizada para este CNPJ/UF.'
        resultado.erro_codigo = 'IE_NAO_LOCALIZADA'
        return resultado

    resultado.mensagem_usuario = x_motivo or 'Consulta SEFAZ indisponível no momento.'
    resultado.erro_codigo = f'SEFAZ_{c_stat or "ERRO"}'
    return resultado
