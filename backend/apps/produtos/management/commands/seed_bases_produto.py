"""Popula polegadas (IDs oficiais), schedules, roscas/conexões e famílias de exemplo."""

from django.core.management.base import BaseCommand

from apps.produtos.models import (
    FamiliaProduto,
    FamiliaProdutoPolegadaPermitida,
    FamiliaProdutoRoscaConexaoPermitida,
    FamiliaProdutoSchedulePermitido,
    Polegada,
    RoscaConexao,
    ScheduleEspessura,
)
from apps.produtos.roscas_conexao_base import seed_roscas_conexao_canonicas

POLEGADAS_OFICIAIS = [
    ('01', '1/8"'),
    ('02', '1/4"'),
    ('03', '3/8"'),
    ('04', '1/2"'),
    ('05', '3/4"'),
    ('06', '1"'),
    ('07', '1.1/4"'),
    ('08', '1.1/2"'),
    ('09', '2"'),
    ('10', '2.1/4"'),
    ('11', '2.1/2"'),
    ('12', '3"'),
    ('13', '3.1/4"'),
    ('14', '3.1/2"'),
    ('15', '4"'),
    ('16', '5"'),
    ('17', '6"'),
    ('18', '6.1/4"'),
    ('19', '8"'),
    ('20', '10"'),
    ('21', '12"'),
    ('22', '14"'),
    ('23', '16"'),
    ('24', '18"'),
    ('25', '20"'),
    ('26', '22"'),
    ('27', '24"'),
    ('28', '26"'),
    ('29', '28"'),
    ('30', '30"'),
    ('31', '32"'),
    ('32', '34"'),
    ('33', '36"'),
    ('34', '38"'),
    ('35', '40"'),
    ('36', '42"'),
    ('37', '44"'),
    ('38', '46"'),
    ('39', '48"'),
    ('40', '2.3/4"'),
]


class Command(BaseCommand):
    help = 'Popula polegadas, schedules, roscas/conexão e famílias de exemplo (idempotente).'

    def handle(self, *args, **options):
        for codigo, descricao in POLEGADAS_OFICIAIS:
            Polegada.objects.update_or_create(
                tipo_medida=Polegada.TipoMedida.NPS,
                codigo_oficial=codigo,
                defaults={'codigo': codigo, 'descricao': descricao, 'origem': 'SEED_BASES_NPS'},
            )
        self.stdout.write(self.style.SUCCESS(f'Polegadas: {len(POLEGADAS_OFICIAIS)} registros garantidos.'))

        for codigo, desc, aplicacao, ordem in [
            ('40', 'SCH 40', ScheduleEspessura.Aplicacao.CARBONO, 50),
            ('80', 'SCH 80', ScheduleEspessura.Aplicacao.CARBONO, 70),
            ('160', 'SCH 160', ScheduleEspessura.Aplicacao.CARBONO, 110),
            ('10S', 'SCH 10S', ScheduleEspessura.Aplicacao.INOX, 160),
            ('SCH40', 'Schedule 40', ScheduleEspessura.Aplicacao.OUTRO, 900),
            ('SCH80', 'Schedule 80', ScheduleEspessura.Aplicacao.OUTRO, 910),
            ('SCH160', 'Schedule 160', ScheduleEspessura.Aplicacao.OUTRO, 920),
        ]:
            ScheduleEspessura.objects.update_or_create(
                codigo_schedule=codigo,
                defaults={'codigo': codigo, 'descricao': desc, 'aplicacao': aplicacao, 'ordem': ordem, 'ativo': True},
            )
        self.stdout.write(self.style.SUCCESS('Schedules: OK.'))

        seed_roscas_conexao_canonicas()
        self.stdout.write(self.style.SUCCESS('Roscas / conexões: OK.'))

        t = FamiliaProduto.TipoRegraCodigo
        familias = [
            dict(
                codigo_figura='2024',
                descricao_base='VALVULA ESFERA TRIPARTIDA TOTAL INOX 304 TP BSP',
                tipo_regra_codigo=t.BASE_POLEGADA,
                separador_base_medidas='.',
                ncm_padrao='8481.80.95',
                unidade_padrao='PC',
            ),
            dict(
                codigo_figura='2023',
                descricao_base='VALVULA ESFERA TRIPARTIDA WCB PP TP',
                tipo_regra_codigo=t.BASE_ROSCA_POLEGADA,
                separador_base_medidas='.',
                ncm_padrao='8481.80.95',
                unidade_padrao='PC',
            ),
            dict(
                codigo_figura='0052',
                descricao_base='NIPLE REDUCAO LATAO BSP',
                tipo_regra_codigo=t.BASE_DUAS_POLEGADAS,
                separador_base_medidas='.',
                unidade_padrao='PC',
            ),
            dict(
                codigo_figura='0114',
                descricao_base='REDUCAO EXCENTRICA ACO CARBONO',
                tipo_regra_codigo=t.BASE_SCHEDULE_DUAS_POLEGADAS,
                separador_base_medidas='.',
                unidade_padrao='PC',
            ),
            dict(
                codigo_figura='6118',
                descricao_base='TUBO S/C ACO CARBONO API 5L PSL-1',
                tipo_regra_codigo=t.BASE_SCHEDULE_POLEGADA,
                separador_base_medidas='.',
                unidade_padrao='M',
            ),
            dict(
                codigo_figura='6038',
                descricao_base='VALVULA BORBOLETA WAFER BIEXCENTRICA 300#',
                tipo_regra_codigo=t.UNDERSCORE_POLEGADA,
                separador_base_medidas='_',
                unidade_padrao='PC',
            ),
        ]
        rosca_bsp = RoscaConexao.objects.filter(codigo='').first()
        schedule_40 = ScheduleEspessura.objects.filter(codigo_schedule='40').first()
        polegadas_map = {
            p.codigo: p
            for p in Polegada.objects.filter(tipo_medida=Polegada.TipoMedida.NPS)
        }
        for row in familias:
            obj, _ = FamiliaProduto.objects.update_or_create(
                codigo_figura=row['codigo_figura'],
                defaults={**{k: v for k, v in row.items() if k != 'codigo_figura'}, 'ativo': True},
            )
            obj.save()
            # relações iniciais mínimas para viabilizar cadastro guiado.
            for cod in ('04', '05', '06', '07', '08', '09', '12', '15'):
                p = polegadas_map.get(cod)
                if p:
                    FamiliaProdutoPolegadaPermitida.objects.get_or_create(
                        familia=obj,
                        polegada=p,
                        tipo=FamiliaProdutoPolegadaPermitida.TipoPolegada.AMBAS,
                        defaults={'ativo': True},
                    )
            if rosca_bsp:
                FamiliaProdutoRoscaConexaoPermitida.objects.get_or_create(
                    familia=obj,
                    rosca_conexao=rosca_bsp,
                    defaults={'padrao_da_familia': True, 'ativo': True},
                )
            if schedule_40 and obj.usa_schedule:
                FamiliaProdutoSchedulePermitido.objects.get_or_create(
                    familia=obj,
                    schedule=schedule_40,
                    defaults={'padrao_da_familia': True, 'ativo': True},
                )
        self.stdout.write(self.style.SUCCESS(f'Famílias exemplo: {len(familias)} registros.'))
