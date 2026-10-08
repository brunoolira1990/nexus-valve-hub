"""Cenário fiscal de entrada: escopos, vínculo de folhas, matriz e cópia."""

from __future__ import annotations

from copy import copy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict

from django.core.exceptions import ValidationError
from django.db import models, transaction

if TYPE_CHECKING:
    from apps.regras_fiscais.models import (
        CenarioFiscalEntrada,
        CenarioFiscalEntradaEscopo,
        RegraFiscalEntrada,
    )

NOME_CENARIO_PADRAO = 'Cenário Padrão'

UFS_BRASIL = (
    'AC',
    'AL',
    'AP',
    'AM',
    'BA',
    'CE',
    'DF',
    'ES',
    'GO',
    'MA',
    'MT',
    'MS',
    'MG',
    'PA',
    'PB',
    'PR',
    'PE',
    'PI',
    'RJ',
    'RN',
    'RS',
    'RO',
    'RR',
    'SC',
    'SP',
    'SE',
    'TO',
)

STATUS_CONFIGURADO = 'CONFIGURADO'
STATUS_INCOMPLETO = 'INCOMPLETO'
STATUS_SEM_CONFIGURACAO = 'SEM_CONFIGURACAO'


class DestinoConfiguracaoDict(TypedDict, total=False):
    uf_origem: str
    uf_destino: str
    cfop_origem: str
    cfop_entrada: str


class ResultadoCopiaConfiguracaoDict(TypedDict):
    criados: list[int]
    atualizados: list[int]
    ignorados: list[dict[str, Any]]


def _only_digits_cfop(value: str) -> str:
    return ''.join(c for c in (value or '') if c.isdigit())


def cfop_origem_regra(regra: RegraFiscalEntrada) -> str:
    return _only_digits_cfop((regra.cfop_origem or '').strip() or (regra.cfop or '').strip())


def label_escopo(escopo: CenarioFiscalEntradaEscopo) -> str:
    from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo as EscopoModel

    if escopo.tipo_escopo == EscopoModel.TipoEscopo.GERAL:
        return 'Regra geral'
    if escopo.tipo_escopo == EscopoModel.TipoEscopo.PRODUTO:
        pid = escopo.produto_id or 0
        return f'Produto {pid}'
    ncm = (escopo.ncm or '').strip()
    if escopo.tipo_escopo == EscopoModel.TipoEscopo.NCM_PREFIXO:
        return f'NCM {ncm} (prefixo)' if ncm else 'NCM prefixo'
    return f'NCM {ncm}' if ncm else 'NCM'


def inferir_tipo_escopo_regra(regra: RegraFiscalEntrada) -> str:
    from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo

    if regra.produto_id:
        return CenarioFiscalEntradaEscopo.TipoEscopo.PRODUTO
    ncm = (regra.ncm or '').strip()
    if ncm and regra.ncm_prefixo:
        return CenarioFiscalEntradaEscopo.TipoEscopo.NCM_PREFIXO
    if ncm:
        return CenarioFiscalEntradaEscopo.TipoEscopo.NCM
    return CenarioFiscalEntradaEscopo.TipoEscopo.GERAL


def chave_escopo_regra(regra: RegraFiscalEntrada) -> tuple[str, str, int | None]:
    tipo = inferir_tipo_escopo_regra(regra)
    if tipo == 'PRODUTO':
        return tipo, '', regra.produto_id
    return tipo, (regra.ncm or '').strip(), None


def obter_ou_criar_cenario_padrao() -> 'CenarioFiscalEntrada':
    from apps.regras_fiscais.models import CenarioFiscalEntrada

    existente = (
        CenarioFiscalEntrada.objects.filter(padrao=True)
        .order_by('-ativo', 'id')
        .first()
    )
    if existente:
        updates: list[str] = []
        if not existente.ativo:
            existente.ativo = True
            updates.append('ativo')
        if existente.nome != NOME_CENARIO_PADRAO and not existente.nome.strip():
            existente.nome = NOME_CENARIO_PADRAO
            updates.append('nome')
        if updates:
            existente.save(update_fields=updates)
        return existente
    return CenarioFiscalEntrada.objects.create(
        nome=NOME_CENARIO_PADRAO,
        ativo=True,
        padrao=True,
        observacoes='Cenário criado automaticamente para regras de entrada existentes.',
    )


def get_or_create_cenario_padrao() -> 'CenarioFiscalEntrada':
    """Alias em inglês para integrações e testes."""
    return obter_ou_criar_cenario_padrao()


def vincular_regras_orfas_ao_cenario_padrao(*, limite: int = 500) -> int:
    """Associa regras legadas sem cenário/escopo ao Cenário Padrão (idempotente)."""
    from apps.regras_fiscais.models import RegraFiscalEntrada

    qs = RegraFiscalEntrada.objects.filter(
        models.Q(cenario_id__isnull=True) | models.Q(escopo_id__isnull=True),
    ).order_by('id')[:limite]
    vinculadas = 0
    for regra in qs:
        associar_cenario_e_escopo_regra(regra)
        regra.save()
        vinculadas += 1
    return vinculadas


def garantir_cenarios_entrada_para_api() -> None:
    """Garante cenário padrão e vínculo de regras órfãs antes da listagem na UI."""
    obter_ou_criar_cenario_padrao()
    vincular_regras_orfas_ao_cenario_padrao()


def obter_ou_criar_escopo(
    cenario: CenarioFiscalEntrada,
    *,
    tipo_escopo: str,
    ncm: str = '',
    produto_id: int | None = None,
) -> CenarioFiscalEntradaEscopo:
    from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo

    escopo, _ = CenarioFiscalEntradaEscopo.objects.get_or_create(
        cenario=cenario,
        tipo_escopo=tipo_escopo,
        ncm=(ncm or '').strip(),
        produto_id=produto_id if tipo_escopo == CenarioFiscalEntradaEscopo.TipoEscopo.PRODUTO else None,
        defaults={'ativo': True, 'prioridade_escopo': 10},
    )
    return escopo


def obter_ou_criar_escopo_para_regra(
    regra: RegraFiscalEntrada,
    cenario: CenarioFiscalEntrada | None = None,
) -> CenarioFiscalEntradaEscopo:
    cenario = cenario or regra.cenario or obter_ou_criar_cenario_padrao()
    tipo, ncm, produto_id = chave_escopo_regra(regra)
    return obter_ou_criar_escopo(cenario, tipo_escopo=tipo, ncm=ncm, produto_id=produto_id)


def sincronizar_campos_match_do_escopo(regra: RegraFiscalEntrada) -> None:
    if not regra.escopo_id:
        return
    from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo as EscopoModel

    escopo = regra.escopo
    if escopo is None:
        escopo = EscopoModel.objects.filter(pk=regra.escopo_id).first()
    if escopo is None:
        return

    if escopo.tipo_escopo == EscopoModel.TipoEscopo.PRODUTO:
        regra.produto_id = escopo.produto_id
        regra.ncm = ''
        regra.ncm_prefixo = False
    elif escopo.tipo_escopo == EscopoModel.TipoEscopo.NCM_PREFIXO:
        regra.ncm = escopo.ncm
        regra.ncm_prefixo = True
        regra.produto = None
    elif escopo.tipo_escopo == EscopoModel.TipoEscopo.NCM:
        regra.ncm = escopo.ncm
        regra.ncm_prefixo = False
        regra.produto = None
    elif escopo.tipo_escopo == EscopoModel.TipoEscopo.GERAL:
        regra.ncm = ''
        regra.ncm_prefixo = False
        regra.produto = None


def gerar_label_configuracao_fiscal(
    regra: RegraFiscalEntrada,
    escopo: CenarioFiscalEntradaEscopo | None = None,
) -> str:
    escopo = escopo or getattr(regra, 'escopo', None)
    if escopo is None and regra.escopo_id:
        from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo

        escopo = CenarioFiscalEntradaEscopo.objects.filter(pk=regra.escopo_id).first()

    if escopo:
        escopo_label = label_escopo(escopo)
    else:
        tipo = inferir_tipo_escopo_regra(regra)
        from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo as EscopoModel

        escopo_label = label_escopo(
            EscopoModel(
                tipo_escopo=tipo,
                ncm=(regra.ncm or '').strip(),
                produto_id=regra.produto_id,
                ncm_prefixo=regra.ncm_prefixo,
            ),
        )

    ufo = (regra.uf_origem or '').strip().upper()[:2] or '*'
    ufd = (regra.uf_destino or '').strip().upper()[:2] or '*'
    cfop_o = cfop_origem_regra(regra) or '?'
    cfop_e = _only_digits_cfop(regra.cfop_entrada or '') or '?'
    return f'{escopo_label} · {ufo}→{ufd} · {cfop_o}→{cfop_e}'


def aplicar_rotulo_automatico_regra(regra: RegraFiscalEntrada) -> None:
    if (regra.descricao_cenario or '').strip():
        return
    label = gerar_label_configuracao_fiscal(regra)
    regra.descricao_cenario = label
    if not (regra.nome or '').strip() or (regra.nome or '').strip().startswith('Regra entrada'):
        regra.nome = label[:120]


@transaction.atomic
def associar_cenario_e_escopo_regra(regra: RegraFiscalEntrada) -> None:
    """Garante cenario/escopo e sincroniza critérios de match da folha."""
    from apps.regras_fiscais.models import CenarioFiscalEntradaEscopo

    if regra.escopo_id:
        if regra.escopo is None:
            regra.escopo = CenarioFiscalEntradaEscopo.objects.filter(pk=regra.escopo_id).first()
        if regra.escopo and not regra.cenario_id:
            regra.cenario_id = regra.escopo.cenario_id
        sincronizar_campos_match_do_escopo(regra)
    else:
        if not regra.cenario_id:
            regra.cenario = obter_ou_criar_cenario_padrao()
        escopo = obter_ou_criar_escopo_para_regra(regra, cenario=regra.cenario)
        regra.escopo = escopo
        sincronizar_campos_match_do_escopo(regra)
    aplicar_rotulo_automatico_regra(regra)


def _norm_uf(value: str | None) -> str:
    return (value or '').strip().upper()[:2]


def chave_configuracao_regra(
    *,
    uf_origem: str = '',
    uf_destino: str = '',
    cfop_origem: str = '',
    cfop_entrada: str = '',
) -> tuple[str, str, str, str]:
    return (
        _norm_uf(uf_origem),
        _norm_uf(uf_destino),
        _only_digits_cfop(cfop_origem),
        _only_digits_cfop(cfop_entrada),
    )


def chave_configuracao_de_regra(regra: RegraFiscalEntrada) -> tuple[str, str, str, str]:
    return chave_configuracao_regra(
        uf_origem=regra.uf_origem,
        uf_destino=regra.uf_destino,
        cfop_origem=cfop_origem_regra(regra),
        cfop_entrada=regra.cfop_entrada or '',
    )


def _str_preenchido(val: str | None) -> bool:
    return bool((val or '').strip())


def _dec_preenchido(val: Decimal | None) -> bool:
    return val is not None


def regra_tem_bloco_fiscal_ou_efeito(regra: RegraFiscalEntrada) -> bool:
    """Ao menos um imposto/efeito além dos defaults neutros."""
    if any(
        [
            _str_preenchido(regra.cst_icms_esperado),
            _str_preenchido(regra.csosn_esperado),
            _str_preenchido(regra.modalidade_bc_icms),
            _dec_preenchido(regra.aliquota_icms),
            _str_preenchido(regra.cst_ipi_esperado),
            _dec_preenchido(regra.aliquota_ipi),
            _str_preenchido(regra.cst_pis_esperado),
            _dec_preenchido(regra.aliquota_pis),
            _str_preenchido(regra.cst_cofins_esperado),
            _dec_preenchido(regra.aliquota_cofins),
            regra.icms_st_aplicavel is not None,
            _str_preenchido(regra.mensagem_padrao),
            (regra.observacoes or '').strip(),
        ],
    ):
        return True
    if regra.exige_certificado_fornecedor:
        return True
    if regra.movimenta_estoque is False:
        return True
    if regra.permite_credito_fiscal is False:
        return True
    from apps.regras_fiscais.models import RegraFiscalEntrada as RFE

    return regra.severidade != RFE.Severidade.INFORMATIVO


def classificar_status_configuracao(regra: RegraFiscalEntrada) -> str:
    cfop_o = cfop_origem_regra(regra)
    cfop_e = _only_digits_cfop(regra.cfop_entrada or '')
    if cfop_o and cfop_e and regra_tem_bloco_fiscal_ou_efeito(regra):
        return STATUS_CONFIGURADO
    if cfop_o or cfop_e or _norm_uf(regra.uf_origem) or _norm_uf(regra.uf_destino):
        return STATUS_INCOMPLETO
    return STATUS_INCOMPLETO


def montar_resumo_impostos_regra(regra: RegraFiscalEntrada) -> dict[str, str]:
    from apps.regras_fiscais.entrada_fiscal import _montar_impostos_esperados

    snap = _montar_impostos_esperados(regra)

    def icms() -> str:
        if not snap.get('cst_icms') and not snap.get('csosn') and not snap.get('aliquota_fcp'):
            return ''
        cst = snap.get('cst_icms') or snap.get('csosn') or ''
        s = f'CST {cst}' if cst else 'ICMS'
        if snap.get('aliquota_icms'):
            s += f' · {snap["aliquota_icms"]}%'
        if snap.get('aliquota_fcp'):
            s += f' · FCP {snap["aliquota_fcp"]}%'
        elif snap.get('fcp_aplicavel') == 'Sim':
            s += ' · FCP'
        return s

    def ipi() -> str:
        if not snap.get('cst_ipi'):
            return ''
        s = f'CST {snap["cst_ipi"]}'
        if snap.get('aliquota_ipi'):
            s += f' · {snap["aliquota_ipi"]}%'
        return s

    def pis() -> str:
        if not snap.get('cst_pis'):
            return ''
        s = f'CST {snap["cst_pis"]}'
        if snap.get('aliquota_pis'):
            s += f' · {snap["aliquota_pis"]}%'
        return s

    def cofins() -> str:
        if not snap.get('cst_cofins'):
            return ''
        s = f'CST {snap["cst_cofins"]}'
        if snap.get('aliquota_cofins'):
            s += f' · {snap["aliquota_cofins"]}%'
        return s

    return {
        'icms': icms(),
        'ipi': ipi(),
        'pis': pis(),
        'cofins': cofins(),
    }


def serializar_configuracao_matriz(regra: RegraFiscalEntrada) -> dict[str, Any]:
    from apps.regras_fiscais.reforma_tributaria_config import reforma_tributaria_preenchida
    from apps.regras_fiscais.regras_fiscais_minimas import (
        pendencias_regra_entrada_incompleta,
        regra_entrada_esta_incompleta,
    )
    from apps.cadastros.models import Empresa

    empresa = Empresa.objects.order_by('pk').first()
    regime = (empresa.regime_tributario or '').strip() if empresa else ''

    resumo = montar_resumo_impostos_regra(regra)
    return {
        'id': regra.id,
        'uf_origem': _norm_uf(regra.uf_origem) or '',
        'uf_destino': _norm_uf(regra.uf_destino) or '',
        'cfop_origem': cfop_origem_regra(regra),
        'cfop_entrada': _only_digits_cfop(regra.cfop_entrada or ''),
        'status_configuracao': classificar_status_configuracao(regra),
        'incompleta': bool(regra.ativo and regra_entrada_esta_incompleta(regra, regime)),
        'pendencias_fiscais': pendencias_regra_entrada_incompleta(regra, regime),
        'label_configuracao': gerar_label_configuracao_fiscal(regra),
        'resumo_impostos': resumo,
        'tem_reforma': reforma_tributaria_preenchida(regra.reforma_tributaria),
        'efeitos': {
            'movimenta_estoque': regra.movimenta_estoque,
            'exige_certificado_fornecedor': regra.exige_certificado_fornecedor,
            'permite_credito_fiscal': regra.permite_credito_fiscal,
            'severidade': regra.severidade,
        },
        'ativo': regra.ativo,
    }


def montar_matriz_escopo(escopo: CenarioFiscalEntradaEscopo) -> dict[str, Any]:
    from apps.regras_fiscais.models import RegraFiscalEntrada

    regras = list(
        RegraFiscalEntrada.objects.filter(escopo=escopo)
        .select_related('escopo', 'cenario')
        .order_by('uf_origem', 'uf_destino', 'cfop_origem', 'cfop_entrada', 'id'),
    )
    ufs_presentes: set[str] = set()
    configuracoes = []
    for regra in regras:
        if _norm_uf(regra.uf_origem):
            ufs_presentes.add(_norm_uf(regra.uf_origem))
        if _norm_uf(regra.uf_destino):
            ufs_presentes.add(_norm_uf(regra.uf_destino))
        configuracoes.append(serializar_configuracao_matriz(regra))

    ufs_sem = sorted(u for u in UFS_BRASIL if u not in ufs_presentes)
    return {
        'escopo': {
            'id': escopo.id,
            'tipo_escopo': escopo.tipo_escopo,
            'ncm': (escopo.ncm or '').strip(),
            'produto_id': escopo.produto_id,
            'label': label_escopo(escopo),
        },
        'configuracoes': configuracoes,
        'ufs_sem_configuracao': ufs_sem,
    }


def _campos_copia_fiscal() -> list[str]:
    from apps.regras_fiscais.models import RegraFiscalEntrada

    excluir = {'id', 'criado_em', 'atualizado_em'}
    return [
        f.name
        for f in RegraFiscalEntrada._meta.fields
        if f.name not in excluir and not f.primary_key
    ]


def _clonar_regra_fiscal(origem: RegraFiscalEntrada) -> RegraFiscalEntrada:
    from apps.regras_fiscais.models import RegraFiscalEntrada

    nova = RegraFiscalEntrada()
    for nome in _campos_copia_fiscal():
        setattr(nova, nome, copy(getattr(origem, nome)))
    nova.descricao_cenario = ''
    return nova


def _aplicar_destino_regra(regra: RegraFiscalEntrada, destino: DestinoConfiguracaoDict) -> None:
    if 'uf_origem' in destino:
        regra.uf_origem = _norm_uf(destino.get('uf_origem', ''))
    if 'uf_destino' in destino:
        regra.uf_destino = _norm_uf(destino.get('uf_destino', ''))
    if 'cfop_origem' in destino and destino['cfop_origem'] is not None:
        co = _only_digits_cfop(destino['cfop_origem'])
        regra.cfop_origem = co
        regra.cfop = co
    if 'cfop_entrada' in destino and destino['cfop_entrada'] is not None:
        regra.cfop_entrada = _only_digits_cfop(destino['cfop_entrada'])


def _buscar_regra_por_chave(
    escopo: CenarioFiscalEntradaEscopo,
    chave: tuple[str, str, str, str],
    *,
    excluir_id: int | None = None,
) -> RegraFiscalEntrada | None:
    from apps.regras_fiscais.models import RegraFiscalEntrada

    for regra in RegraFiscalEntrada.objects.filter(escopo=escopo):
        if excluir_id and regra.id == excluir_id:
            continue
        if chave_configuracao_de_regra(regra) == chave:
            return regra
    return None


def _copiar_campos_fiscais_de_origem(destino: RegraFiscalEntrada, origem: RegraFiscalEntrada) -> None:
    preservar = {
        'id',
        'criado_em',
        'atualizado_em',
        'cenario',
        'cenario_id',
        'escopo',
        'escopo_id',
        'uf_origem',
        'uf_destino',
        'cfop',
        'cfop_origem',
        'cfop_entrada',
        'descricao_cenario',
        'nome',
    }
    for nome in _campos_copia_fiscal():
        if nome in preservar:
            continue
        setattr(destino, nome, copy(getattr(origem, nome)))


@transaction.atomic
def duplicar_regra_fiscal_entrada(
    regra_id: int,
    destino: DestinoConfiguracaoDict,
    *,
    sobrescrever: bool = False,
) -> RegraFiscalEntrada:
    from apps.regras_fiscais.models import RegraFiscalEntrada

    origem = RegraFiscalEntrada.objects.select_related('escopo', 'cenario').get(pk=regra_id)
    if not origem.escopo_id:
        raise ValidationError('Regra sem escopo não pode ser duplicada por esta action.')

    nova = _clonar_regra_fiscal(origem)
    _aplicar_destino_regra(nova, destino)
    nova.cenario_id = origem.cenario_id
    nova.escopo_id = origem.escopo_id
    associar_cenario_e_escopo_regra(nova)

    chave = chave_configuracao_de_regra(nova)
    existente = _buscar_regra_por_chave(origem.escopo, chave, excluir_id=origem.id)
    if existente and not sobrescrever:
        raise ValidationError(
            f'Já existe configuração para {chave[0] or "*"}→{chave[1] or "*"} '
            f'CFOP {chave[2] or "?"}→{chave[3] or "?"}. Use sobrescrever=true para substituir.',
        )
    if existente and sobrescrever:
        _copiar_campos_fiscais_de_origem(existente, origem)
        _aplicar_destino_regra(existente, destino)
        existente.descricao_cenario = ''
        associar_cenario_e_escopo_regra(existente)
        existente.save()
        return existente

    nova.save()
    return nova


@transaction.atomic
def copiar_configuracao_escopo(
    escopo: CenarioFiscalEntradaEscopo,
    *,
    origem_regra_id: int,
    destinos: list[DestinoConfiguracaoDict],
    sobrescrever: bool = False,
) -> ResultadoCopiaConfiguracaoDict:
    from apps.regras_fiscais.models import RegraFiscalEntrada

    origem = RegraFiscalEntrada.objects.get(pk=origem_regra_id, escopo=escopo)
    criados: list[int] = []
    atualizados: list[int] = []
    ignorados: list[dict[str, Any]] = []

    for dest in destinos:
        chave = chave_configuracao_regra(
            uf_origem=dest.get('uf_origem', ''),
            uf_destino=dest.get('uf_destino', ''),
            cfop_origem=dest.get('cfop_origem', cfop_origem_regra(origem)),
            cfop_entrada=dest.get('cfop_entrada', origem.cfop_entrada or ''),
        )
        existente = _buscar_regra_por_chave(escopo, chave)
        if existente and not sobrescrever:
            ignorados.append(
                {
                    'destino': dest,
                    'regra_id': existente.id,
                    'motivo': 'Configuração já existe para esta UF/CFOP.',
                },
            )
            continue

        if existente and sobrescrever:
            _copiar_campos_fiscais_de_origem(existente, origem)
            _aplicar_destino_regra(existente, dest)
            existente.descricao_cenario = ''
            associar_cenario_e_escopo_regra(existente)
            existente.save()
            atualizados.append(existente.id)
            continue

        nova = _clonar_regra_fiscal(origem)
        _aplicar_destino_regra(nova, dest)
        nova.cenario_id = origem.cenario_id
        nova.escopo_id = origem.escopo_id
        associar_cenario_e_escopo_regra(nova)
        nova.save()
        criados.append(nova.id)

    return {
        'criados': criados,
        'atualizados': atualizados,
        'ignorados': ignorados,
    }
