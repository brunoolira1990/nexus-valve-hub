"""
Auditoria somente leitura — FamiliaProduto.codigo_figura (ERP 4.0.14.x).

Garantias:
- Não chama save/create/update/delete/get_or_create.
- Não reserva código nem incrementa contador.
- Funciona antes da migration 0027.
- Exibe somente códigos de família e estatísticas agregadas.
- Não exibe descrições, preços, NCM ou dados de produto além de contagens.
- Classifica sufixos pelo template (não trata todo NNNN+sufixo como legado).
"""

from __future__ import annotations

import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count

from apps.produtos.familia_codigo import (
    ENV_POLITICA,
    PoliticaPrefixoCodigoFigura,
    calcular_proximo_numero_inicial,
    classificar_codigo_figura_contextual,
    codigo_figura_valido,
    codigos_especiais_com_prefixo,
    extrair_prefixo_numerico,
    maior_codigo_figura_valido_existente,
    maior_prefixo_numerico_existente,
    piso_contador_para_politica,
    proximo_candidato_livre_a_partir_de,
    resolver_config_politica_codigo_figura,
    template_acrescenta_od,
)
from apps.produtos.models import FamiliaProduto

_RE_NNNN = re.compile(r'^\d{4}$')

POLITICA_PRODUCAO = PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_UNICIDADE


def _tabela_sequencia_existe() -> bool:
    return 'produtos_familiaprodutocodigosequencia' in set(connection.introspection.table_names())


def _ler_proximo_numero_sequencia_readonly() -> int | None:
    if not _tabela_sequencia_existe():
        return None
    with connection.cursor() as cur:
        cur.execute(
            'SELECT proximo_numero FROM produtos_familiaprodutocodigosequencia WHERE id = %s LIMIT 1',
            [1],
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def _parecer_por_politica(
    politica: str,
    *,
    nnnn_count: int,
    tecnicos: int,
    repeticoes: int,
    conflitos: int,
) -> str:
    if politica == PoliticaPrefixoCodigoFigura.VALOR_COMPLETO:
        return 'NÃO RECOMENDADO para este ERP — decisão do operador: PREFIXO_GLOBAL_UNICIDADE'
    if politica == PoliticaPrefixoCodigoFigura.PREFIXO_GLOBAL_SEQUENCIAL:
        return 'NÃO USAR neste ERP — operador não escolheu SEQUENCIAL; não criar migration 0028'
    if conflitos > 0:
        return (
            'APTO com revisão — conflito real de prefixo entre famílias de figura '
            '(não alterar dados nesta tarefa)'
        )
    if repeticoes > 0:
        return (
            'APTO com alerta — há código(s) com possível repetição de complemento do template'
        )
    if tecnicos > 0 or nnnn_count > 0:
        return 'APTO — códigos técnicos com sufixo são válidos quando o template não os acrescenta'
    return 'APTO se política explícita e gates operacionais OK'


def _conflitos_prefixo_reais() -> list[dict]:
    """
    Conflito real: duas ou mais famílias de figura (não MANUAL_FABRICANTE)
    compartilham o mesmo prefixo numérico sob PREFIXO_GLOBAL_UNICIDADE.
    """
    por_prefixo: dict[int, list[dict]] = defaultdict(list)
    qs = FamiliaProduto.objects.exclude(
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE,
    ).annotate(n_prod=Count('produtos')).only(
        'id',
        'codigo_figura',
        'tipo_regra_codigo',
        'tipo_dimensional',
    )
    for fam in qs:
        p = extrair_prefixo_numerico(fam.codigo_figura)
        if p is None:
            continue
        por_prefixo[p].append(
            {
                'id': fam.id,
                'codigo': (fam.codigo_figura or '').strip(),
                'regra': fam.tipo_regra_codigo,
                'dimensional': fam.tipo_dimensional,
                'produtos': fam.n_prod,
            },
        )
    out = []
    for prefixo, itens in sorted(por_prefixo.items()):
        codigos = sorted({i['codigo'] for i in itens})
        if len(codigos) > 1:
            out.append({'prefixo': prefixo, 'itens': itens, 'codigos': codigos})
    return out


class Command(BaseCommand):
    help = 'Auditoria read-only de codigo_figura (ERP 4.0.14.x pré-deploy)'

    def handle(self, *args, **options):
        cfg = resolver_config_politica_codigo_figura()
        self.stdout.write(self.style.MIGRATE_HEADING('=== AUDITORIA READ-ONLY: codigo_figura ==='))
        self.stdout.write('Modo: somente leitura — nenhuma escrita no banco.\n')

        self.stdout.write('POLÍTICA DE PRODUÇÃO (decisão do operador):')
        self.stdout.write(f'  Escolhida: {POLITICA_PRODUCAO}')
        self.stdout.write('  Sufixos no codigo_figura são válidos quando o template não os acrescenta.')
        self.stdout.write(f'  Variável: {ENV_POLITICA}')
        self.stdout.write(f'  Configurada agora: {cfg.politica}')
        self.stdout.write(f'  Origem: {cfg.origem}')
        self.stdout.write(f'  Ambiente app: {cfg.ambiente_app}')
        if cfg.alerta_fallback:
            self.stdout.write(self.style.WARNING(f'  ALERTA: {cfg.alerta_fallback}'))
        if cfg.bloqueio_producao:
            self.stdout.write(self.style.ERROR(f'  BLOQUEIO PRODUÇÃO: {cfg.bloqueio_producao}'))
        if cfg.origem == 'explicita' and cfg.politica == POLITICA_PRODUCAO:
            self.stdout.write(self.style.SUCCESS('  Política explícita alinhada à decisão do operador.'))
        elif cfg.politica != POLITICA_PRODUCAO:
            self.stdout.write(
                self.style.WARNING(
                    f'  Divergência: ambiente em {cfg.politica}; produção deve usar {POLITICA_PRODUCAO}.',
                ),
            )

        familias = list(
            FamiliaProduto.objects.annotate(n_prod=Count('produtos')).only(
                'id',
                'codigo_figura',
                'tipo_regra_codigo',
                'tipo_dimensional',
                'categoria_produto',
            ),
        )
        total = len(familias)

        cats: dict[str, list] = defaultdict(list)
        for fam in familias:
            cat = classificar_codigo_figura_contextual(
                codigo=fam.codigo_figura or '',
                tipo_regra_codigo=fam.tipo_regra_codigo,
            )
            cats[cat].append(fam)

        nnnn = cats.get('NNNN', [])
        tecnicos = cats.get('TECNICO_SUFIXO_VALIDO', [])
        repeticoes = cats.get('POSSIVEL_REPETICAO_TEMPLATE', [])
        manuais_fab = cats.get('MANUAL_FABRICANTE', [])
        outros = cats.get('OUTRO', [])
        conflitos = _conflitos_prefixo_reais()
        especiais_figura = codigos_especiais_com_prefixo()

        self.stdout.write(f'\n1. Total de famílias: {total}')
        self.stdout.write(f'2. (a) Famílias numéricas NNNN: {len(nnnn)}')
        self.stdout.write(f'3. (b) Códigos técnicos manuais com sufixo (válidos pelo template): {len(tecnicos)}')
        for fam in tecnicos[:12]:
            self.stdout.write(
                f'   - {fam.codigo_figura}: regra={fam.tipo_regra_codigo} '
                f'dimensional={fam.tipo_dimensional} produtos={fam.n_prod} '
                f'template_acrescenta_OD={"SIM" if template_acrescenta_od(fam.tipo_regra_codigo) else "NÃO"}',
            )
        self.stdout.write(
            f'4. (c) Possível repetição de complemento do template: {len(repeticoes)}'
        )
        for fam in repeticoes[:12]:
            self.stdout.write(
                f'   - {fam.codigo_figura}: regra={fam.tipo_regra_codigo} '
                f'dimensional={fam.tipo_dimensional} produtos={fam.n_prod} '
                '(código termina com OD e template também acrescenta OD)',
            )
        self.stdout.write(f'5. (d) Manual/fabricante (sem formação por família): {len(manuais_fab)}')
        for fam in manuais_fab[:12]:
            self.stdout.write(
                f'   - {fam.codigo_figura}: produtos={fam.n_prod} '
                f'(excluído do diagnóstico de prefixo NNNN)',
            )
        if outros:
            self.stdout.write(f'   Outros: {len(outros)}')
            for fam in outros[:8]:
                self.stdout.write(f'   - {fam.codigo_figura}: regra={fam.tipo_regra_codigo}')

        maior_nnnn = maior_codigo_figura_valido_existente()
        maior_prefixo = maior_prefixo_numerico_existente()
        self.stdout.write(
            f'\n6. Maior NNNN puro (só famílias de figura): {maior_nnnn:04d}'
            if maior_nnnn
            else '\n6. Maior NNNN puro: (nenhum)'
        )
        self.stdout.write(
            f'   Maior prefixo numérico (figura; exclui MANUAL_FABRICANTE): {maior_prefixo:04d}'
            if maior_prefixo
            else '   Maior prefixo numérico: (nenhum)'
        )

        self.stdout.write('7. Próximo candidato por política (sem persistência):')
        for politica in PoliticaPrefixoCodigoFigura.TODAS:
            piso = piso_contador_para_politica(politica)
            livre = proximo_candidato_livre_a_partir_de(piso, politica=politica)
            ini = calcular_proximo_numero_inicial(politica=politica)
            livre_txt = f'{livre:04d}' if livre else 'ESGOTADO'
            marker = ' ← PRODUÇÃO' if politica == POLITICA_PRODUCAO else ''
            if ini <= 9999:
                self.stdout.write(
                    f'   {politica}: piso={piso:04d} proximo_livre={livre_txt} '
                    f'inicial_contador={ini:04d}{marker}',
                )
            else:
                self.stdout.write(f'   {politica}: ESGOTADO{marker}')
            self.stdout.write(
                f'   Parecer: {_parecer_por_politica(politica, nnnn_count=len(nnnn), tecnicos=len(tecnicos), repeticoes=len(repeticoes), conflitos=len(conflitos))}',
            )

        prox_prod = proximo_candidato_livre_a_partir_de(
            piso_contador_para_politica(POLITICA_PRODUCAO),
            politica=POLITICA_PRODUCAO,
        )
        self.stdout.write(
            f'   Próximo em {POLITICA_PRODUCAO}: '
            + (f'{prox_prod:04d}' if prox_prod else 'ESGOTADO')
        )
        self.stdout.write(
            '   Referência produção (lista informada): maior NNNN=8010 → próximo provável 8011 '
            '(condicionado à auditoria direta do banco antes da migration).'
        )
        self.stdout.write(
            f'   Migration 0027 (maior NNNN+1; runtime unicidade): {maior_nnnn + 1:04d} '
            '(0028 NÃO necessária)'
        )

        seq_val = _ler_proximo_numero_sequencia_readonly()
        if seq_val is not None:
            self.stdout.write(f'   Sequência existente (read-only): proximo_numero={seq_val}')
        else:
            self.stdout.write('   Sequência 0027: tabela ainda não existe.')

        self.stdout.write(f'\n8. (e) Conflitos reais de prefixo (famílias de figura): {len(conflitos)}')
        for conf in conflitos[:20]:
            detalhe = ', '.join(
                f'{i["codigo"]}(regra={i["regra"]},prod={i["produtos"]})' for i in conf['itens']
            )
            self.stdout.write(f'   - prefixo {conf["prefixo"]:04d}: {detalhe}')
        if not conflitos:
            self.stdout.write('   Nenhum conflito real de prefixo entre famílias de figura.')

        self.stdout.write('\n9. Exemplos de referência (classificação contextual):')
        self._exemplo_referencia('0023OD', 'técnico válido se template não acrescenta OD')
        self._exemplo_referencia('0075OD', 'técnico válido se template não acrescenta OD')
        self._exemplo_referencia('6119', 'NNNN; template BASE_OD_* deve acrescentar OD no produto')
        self._exemplo_referencia('18900001-04DC', 'manual/fabricante')

        tem_8010 = any((f.codigo_figura or '').strip() == '8010' for f in familias)
        self.stdout.write(f'\n10. Família codigo_figura="8010": {"SIM" if tem_8010 else "NÃO"}')
        acima_8010 = sorted(
            int((f.codigo_figura or '').strip())
            for f in nnnn
            if codigo_figura_valido(f.codigo_figura) and int((f.codigo_figura or '').strip()) > 8010
        )
        self.stdout.write(
            f'11. NNNN acima de 8010: {len(acima_8010)}'
            + (f' — {", ".join(f"{x:04d}" for x in acima_8010[:20])}' if acima_8010 else '')
        )

        self.stdout.write(
            f'\n12. Códigos NNNN+sufixo de figura (ocupam prefixo; não são "legado" automático): '
            f'{len(especiais_figura)}'
        )
        if especiais_figura:
            self.stdout.write(f'    Exemplos: {", ".join(especiais_figura[:12])}')

        parecer = _parecer_por_politica(
            POLITICA_PRODUCAO,
            nnnn_count=len(nnnn),
            tecnicos=len(tecnicos),
            repeticoes=len(repeticoes),
            conflitos=len(conflitos),
        )
        politica_ok = cfg.origem == 'explicita' and cfg.politica == POLITICA_PRODUCAO
        self.stdout.write('\n' + '=' * 60)
        if 'APTO' in parecer and politica_ok:
            self.stdout.write(self.style.SUCCESS(f'PARECER PRODUÇÃO: APTO — {parecer}'))
        elif 'APTO' in parecer and not politica_ok:
            self.stdout.write(
                self.style.WARNING(
                    f'PARECER PRODUÇÃO: BLOQUEADO — configurar {ENV_POLITICA}={POLITICA_PRODUCAO} '
                    f'explicitamente. Diagnóstico: {parecer}',
                ),
            )
        else:
            self.stdout.write(self.style.ERROR(f'PARECER PRODUÇÃO: BLOQUEADO — {parecer}'))

        self.stdout.write('\nGATES OBRIGATÓRIOS ANTES DE SUBIR BACKEND COM 0027:')
        self.stdout.write('  [ ] Backup confirmado')
        self.stdout.write('  [ ] Esta auditoria executada em produção')
        self.stdout.write(f'  [ ] {ENV_POLITICA}={POLITICA_PRODUCAO} (explícita)')
        self.stdout.write('  [ ] Parecer APTO para PREFIXO_GLOBAL_UNICIDADE')
        self.stdout.write('  [ ] Mecanismo de deploy confirmado (manual vs migrate no startup)')

    def _exemplo_referencia(self, codigo: str, nota: str) -> None:
        fam = (
            FamiliaProduto.objects.filter(codigo_figura=codigo)
            .annotate(n_prod=Count('produtos'))
            .only('id', 'codigo_figura', 'tipo_regra_codigo', 'tipo_dimensional')
            .first()
        )
        if not fam:
            self.stdout.write(f'   - {codigo}: NÃO no banco local — {nota}')
            return
        cat = classificar_codigo_figura_contextual(
            codigo=fam.codigo_figura or '',
            tipo_regra_codigo=fam.tipo_regra_codigo,
        )
        self.stdout.write(
            f'   - {codigo}: classe={cat} regra={fam.tipo_regra_codigo} '
            f'dimensional={fam.tipo_dimensional} produtos={fam.n_prod} '
            f'template_acrescenta_OD={"SIM" if template_acrescenta_od(fam.tipo_regra_codigo) else "NÃO"} '
            f'— {nota}',
        )
