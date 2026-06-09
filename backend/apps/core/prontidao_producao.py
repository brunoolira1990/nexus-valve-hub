"""Verificação de prontidão para produção — ERP 4.0.14.8/4.0.14.9/4.0.14.9.2 (somente leitura)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from django.contrib.auth.models import Group
from django.db.models import Count, Q

from apps.cadastros.colaborador_senha import email_operacional_valido
from apps.core.usuario_exibicao import email_eh_tecnico_local

from apps.cadastros.models import Colaborador, Empresa
from apps.financeiro.models import (
    BaixaFinanceira,
    CategoriaFinanceira,
    CentroCusto,
    ContaFinanceira,
    CreditoFinanceiro,
    ParcelaFinanceira,
    TituloFinanceiro,
)
from apps.fiscal.models import NFeSaida
from apps.produtos.models import FamiliaProduto, Ncm, Produto
from apps.regras_fiscais.models import RegraFiscal, RegraFiscalEntrada, RegraFiscalSaida
from apps.regras_fiscais.regras_fiscais_minimas import validar_regras_fiscais_minimas

User = get_user_model()
CENTAVO = Decimal('0.01')
GRUPOS_ADMIN = ('admin', 'administrador')


def _critico(msg: str, **extra) -> dict[str, Any]:
    return {'nivel': 'critico', 'mensagem': msg, **extra}


def _aviso(msg: str, **extra) -> dict[str, Any]:
    return {'nivel': 'aviso', 'mensagem': msg, **extra}


def _ok(msg: str, **extra) -> dict[str, Any]:
    return {'nivel': 'ok', 'mensagem': msg, **extra}


def verificar_financeiro() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    achados: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []

    sem_numero = TituloFinanceiro.objects.filter(Q(numero='') | Q(numero__isnull=True)).count()
    if sem_numero:
        achados.append(_critico(f'{sem_numero} título(s) sem número.'))

    sem_venc_titulo = TituloFinanceiro.objects.filter(data_vencimento__isnull=True).count()
    if sem_venc_titulo:
        achados.append(_critico(f'{sem_venc_titulo} título(s) sem vencimento.'))

    sem_venc_parcela = ParcelaFinanceira.objects.filter(data_vencimento__isnull=True).count()
    if sem_venc_parcela:
        achados.append(_critico(f'{sem_venc_parcela} parcela(s) sem vencimento.'))

    dup_numero = (
        TituloFinanceiro.objects.exclude(numero='')
        .values('numero')
        .annotate(qtd=Count('id'))
        .filter(qtd__gt=1)
        .count()
    )
    if dup_numero:
        achados.append(_critico(f'{dup_numero} número(s) CR/CP duplicado(s).'))

    saldo_neg = TituloFinanceiro.objects.filter(valor_aberto__lt=-CENTAVO).count()
    if saldo_neg:
        achados.append(_critico(f'{saldo_neg} título(s) com saldo negativo.'))

    creditos_inconsistentes = CreditoFinanceiro.objects.filter(saldo__lt=-CENTAVO).count()
    if creditos_inconsistentes:
        achados.append(_critico(f'{creditos_inconsistentes} crédito(s) com saldo inconsistente.'))

    baixas_sem_conta = BaixaFinanceira.objects.filter(
        conta_financeira__isnull=True,
        estornada=False,
    ).count()
    if baixas_sem_conta:
        achados.append(_aviso(f'{baixas_sem_conta} baixa(s) ativa(s) sem conta financeira.'))

    dup_origem = (
        TituloFinanceiro.objects.exclude(origem_tipo=TituloFinanceiro.OrigemTipo.MANUAL)
        .exclude(origem_id__isnull=True)
        .values('origem_tipo', 'origem_id')
        .annotate(qtd=Count('id'))
        .filter(qtd__gt=1)
        .count()
    )
    if dup_origem:
        achados.append(_aviso(f'{dup_origem} origem(ns) externa(s) duplicada(s) em títulos.'))

    padrao_errado = TituloFinanceiro.objects.exclude(
        Q(numero='') | Q(numero__regex=r'^CR-\d{4}-\d{6}$') | Q(numero__regex=r'^CP-\d{4}-\d{6}$'),
    ).count()
    if padrao_errado:
        achados.append(_aviso(f'{padrao_errado} título(s) fora do padrão CR/CP-AAAA-000001.'))

    if CategoriaFinanceira.objects.count() == 0:
        achados.append(_aviso('Nenhuma categoria financeira cadastrada.'))
    if CentroCusto.objects.count() == 0:
        achados.append(_aviso('Nenhum centro de custo cadastrado.'))
    if ContaFinanceira.objects.filter(ativo=True).count() == 0:
        achados.append(_aviso('Nenhuma conta/caixa financeira ativa cadastrada.'))

    if TituloFinanceiro.objects.count() == 0:
        achados.append(_aviso('Nenhum título financeiro no banco (relatórios vazios).'))

    if not any(a['nivel'] == 'critico' for a in achados):
        ok.append(_ok('Financeiro: numeração, vencimentos e saldos consistentes.'))
    return achados, ok


def verificar_usuarios_colaboradores() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    achados: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []

    admin_ativo = User.objects.filter(is_active=True, is_superuser=True).exists()
    if not admin_ativo:
        grupos_admin = Group.objects.filter(name__in=GRUPOS_ADMIN)
        admin_ativo = User.objects.filter(is_active=True, groups__in=grupos_admin).exists()
    if not admin_ativo:
        achados.append(_critico('Nenhum administrador ativo (superusuário ou grupo admin/administrador).'))

    sem_perfil = (
        User.objects.filter(is_active=True)
        .annotate(q_grupos=Count('groups', distinct=True))
        .filter(q_grupos=0, is_superuser=False)
        .count()
    )
    if sem_perfil:
        achados.append(
            _critico(
                f'{sem_perfil} usuário(s) ativo(s) sem perfil/grupo. '
                'Abra Cadastros > Colaboradores > Editar > Acesso ao sistema > Editar acesso para definir um perfil.',
            ),
        )

    sem_senha = 0
    email_invalido = 0
    email_tecnico = 0
    for user in User.objects.filter(is_active=True).only('pk', 'email', 'password', 'username'):
        if not user.is_superuser and not is_password_usable(user.password):
            sem_senha += 1
        if not (user.email or '').strip():
            email_invalido += 1
        elif email_eh_tecnico_local(user.email):
            email_tecnico += 1
        elif not email_operacional_valido(user.email):
            email_invalido += 1

    if sem_senha:
        achados.append(
            _critico(
                f'{sem_senha} usuário(s) ativo(s) sem senha utilizável. '
                'Abra Cadastros > Colaboradores > Editar > Acesso ao sistema para definir perfil ou redefinir senha.',
            ),
        )
    if email_invalido:
        achados.append(
            _critico(
                f'{email_invalido} usuário(s) ativo(s) com e-mail inválido ou ausente. '
                'Corrija em Minha conta ou Cadastros > Colaboradores > Editar > Acesso ao sistema.',
            ),
        )
    if email_tecnico:
        achados.append(
            _critico(
                f'{email_tecnico} usuário(s) ativo(s) com e-mail técnico/local. '
                'Atualize em Colaboradores > Editar > Acesso ao sistema > Editar acesso antes de produção.',
            ),
        )

    staff_sem_perfil = (
        User.objects.filter(is_active=True, is_staff=True, is_superuser=False)
        .annotate(q_grupos=Count('groups', distinct=True))
        .filter(q_grupos=0)
        .count()
    )
    if staff_sem_perfil:
        achados.append(
            _aviso(
                f'{staff_sem_perfil} usuário(s) staff ativo(s) sem perfil/grupo claro — revise em Colaboradores.',
            ),
        )

    emails_dup = (
        User.objects.exclude(Q(email='') | Q(email__isnull=True))
        .values('email')
        .annotate(qtd=Count('id'))
        .filter(qtd__gt=1)
        .count()
    )
    if emails_dup:
        achados.append(_critico(f'{emails_dup} e-mail(s) duplicado(s) entre usuários.'))

    sem_colaborador = (
        User.objects.filter(is_active=True, is_superuser=False)
        .exclude(pk__in=Colaborador.objects.exclude(usuario__isnull=True).values_list('usuario_id', flat=True))
        .count()
    )
    if sem_colaborador:
        achados.append(
            _aviso(
                f'{sem_colaborador} usuário(s) ativo(s) sem colaborador vinculado — nome exibido usa login técnico.',
            ),
        )

    colab_sem_email = Colaborador.objects.filter(ativo=True).filter(Q(email='') | Q(email__isnull=True)).count()
    if colab_sem_email:
        achados.append(_aviso(f'{colab_sem_email} colaborador(es) ativo(s) sem e-mail.'))

    colab_inativo_user_ativo = Colaborador.objects.filter(ativo=False, usuario__is_active=True).count()
    if colab_inativo_user_ativo:
        achados.append(
            _aviso(f'{colab_inativo_user_ativo} colaborador(es) inativo(s) com usuário ativo (revisar vínculo).'),
        )

    colab_sem_usuario = Colaborador.objects.filter(ativo=True, usuario__isnull=True).count()
    if colab_sem_usuario:
        achados.append(_aviso(f'{colab_sem_usuario} colaborador(es) ativo(s) sem usuário de acesso.'))

    if admin_ativo and sem_perfil == 0 and emails_dup == 0 and sem_senha == 0 and email_invalido == 0:
        ok.append(_ok('Usuários e colaboradores: administrador e perfis consistentes.'))
    return achados, ok


def verificar_fiscal() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    achados: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []

    fiscal = validar_regras_fiscais_minimas()
    achados.extend(fiscal['criticos'])
    achados.extend(fiscal['avisos'])
    ok.extend(fiscal['ok'])

    homolog = NFeSaida.objects.filter(
        status_emissao_sefaz=NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
    ).count()
    if homolog:
        achados.append(_aviso(f'{homolog} NF-e Saída autorizada em homologação.'))

    prod_count = NFeSaida.objects.filter(ambiente_emissao='producao').count()
    if prod_count:
        achados.append(_aviso(f'{prod_count} NF-e Saída com ambiente_emissao=producao (revisar).'))

    reais_misturados = 0
    for nf in NFeSaida.objects.filter(cstat_autorizacao='100').exclude(protocolo_autorizacao='').iterator():
        if nf.status_emissao_sefaz != NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
            reais_misturados += 1
    if reais_misturados:
        achados.append(_aviso(f'{reais_misturados} NF-e com autorização que podem ser documentos reais.'))

    return achados, ok, fiscal


def verificar_produtos() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    achados: list[dict[str, Any]] = []
    ok: list[dict[str, Any]] = []
    counts = {
        'produtos': Produto.objects.count(),
        'familias_figuras': FamiliaProduto.objects.count(),
        'ncm': Ncm.objects.count(),
    }

    if counts['produtos'] == 0:
        achados.append(_critico('Nenhum produto cadastrado.'))

    sem_descricao = Produto.objects.filter(Q(descricao='') | Q(descricao__isnull=True)).count()
    if sem_descricao:
        achados.append(_critico(f'{sem_descricao} produto(s) sem descrição (estrutura inválida).'))

    sem_codigo = Produto.objects.filter(
        modo_codigo=Produto.ModoCodigo.MANUAL,
    ).filter(Q(codigo_completo='') | Q(codigo_completo__isnull=True)).count()
    if sem_codigo:
        achados.append(_aviso(f'{sem_codigo} produto(s) manual(is) sem código completo.'))

    if counts['produtos'] > 0 and sem_descricao == 0:
        ok.append(
            _ok(
                f"Produtos preservados: {counts['produtos']}; "
                f"famílias/figuras: {counts['familias_figuras']}; NCM: {counts['ncm']}.",
            ),
        )
    return achados, ok, counts


def verificar_cadastros_struct(counts_prod: dict[str, int]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    achados: list[dict[str, Any]] = []
    preservados = {
        **counts_prod,
        'regras_fiscais': RegraFiscal.objects.count(),
        'regras_fiscais_saida': RegraFiscalSaida.objects.count(),
        'regras_fiscais_entrada': RegraFiscalEntrada.objects.count(),
        'empresa_emitente': Empresa.objects.count(),
        'usuarios': User.objects.count(),
        'colaboradores': Colaborador.objects.count(),
        'grupos': Group.objects.count(),
    }
    if preservados['empresa_emitente'] == 0:
        achados.append(_critico('Empresa emitente ausente.'))
    return achados, preservados


def executar_verificacao_prontidao() -> dict[str, Any]:
    fin, ok_fin = verificar_financeiro()
    usr, ok_usr = verificar_usuarios_colaboradores()
    fiscal, ok_fiscal, fiscal_detalhe = verificar_fiscal()
    prod, ok_prod, counts_prod = verificar_produtos()
    cad, preservados = verificar_cadastros_struct(counts_prod)

    todos = fin + usr + fiscal + prod + cad
    ok_itens = ok_fin + ok_usr + ok_fiscal + ok_prod
    criticos = [a for a in todos if a['nivel'] == 'critico']
    avisos = [a for a in todos if a['nivel'] == 'aviso']

    checklist = [
        {'item': 'DEBUG=False', 'ok': not settings.DEBUG, 'nota': 'Conferir antes de produção.'},
        {'item': 'Backup realizado', 'ok': False, 'nota': 'Confirmar manualmente antes da limpeza real.'},
        {'item': 'Dados de teste limpos', 'ok': False, 'nota': 'Executar dry-run e limpeza com confirmação.'},
        {'item': 'Administrador ativo', 'ok': not any('administrador' in c['mensagem'].lower() for c in criticos), 'nota': ''},
        {'item': 'Produtos preservados', 'ok': preservados.get('produtos', 0) > 0, 'nota': ''},
        {'item': 'Relatório sem erros críticos', 'ok': len(criticos) == 0, 'nota': ''},
    ]

    return {
        'criticos': criticos,
        'avisos': avisos,
        'ok': ok_itens,
        'preservados': preservados,
        'checklist_producao': checklist,
        'fiscal': {
            'metricas': fiscal_detalhe.get('metricas', {}),
            'checklist_fiscal': fiscal_detalhe.get('checklist_fiscal', []),
            'checklist_saida': fiscal_detalhe.get('checklist_saida', []),
            'checklist_entrada': fiscal_detalhe.get('checklist_entrada', []),
            'criticos': fiscal_detalhe.get('criticos', []),
            'avisos': fiscal_detalhe.get('avisos', []),
            'avisos_entrada': fiscal_detalhe.get('avisos_entrada', []),
            'bloqueios_por_fluxo': fiscal_detalhe.get('bloqueios_por_fluxo', {}),
        },
        'pronto': len(criticos) == 0,
    }
