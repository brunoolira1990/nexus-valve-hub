"""Sprint 3.10 — DIFAL por UF destino: tabela de alíquotas, precedência regra > tabela e fórmula."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.fiscal.difal_retificacao import (
    analisar_difal_retificacao,
    formatar_relatorio_difal_retificacao,
    interestadual_regiao,
)
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.validacao_nfe_saida import (
    TIPO_ALERTA,
    validar_nfe_saida_para_emissao,
)
from apps.fiscal.nfe_difal_calculo import (
    calcular_difal_item,
    resolver_aliquotas_difal,
    validar_parametros_difal_regra,
)
from apps.regras_fiscais.aliquotas_uf_seed import (
    ALICOTAS_ICMS_UF,
    UF_FAIXA_INTERESTADUAL_12,
    interestadual_padrao_para_uf,
)
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import AliquotaIcmsUF, CenarioFiscalSaidaEscopo, RegraFiscalSaida


class DifalAliquotasUfTestsBase(TestCase):
    def setUp(self):
        self.cenario = garantir_cenario_saida_padrao()
        self.escopo = CenarioFiscalSaidaEscopo.objects.get_or_create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.GERAL,
            defaults={'ativo': True},
        )[0]

    def _criar_regra(self, **kwargs) -> RegraFiscalSaida:
        kwargs.setdefault('nome', 'Configuração')
        kwargs.setdefault('difal_aplicavel', True)
        kwargs.setdefault('cfop_venda', '6108')
        kwargs.setdefault('cst_icms', '00')
        return RegraFiscalSaida.objects.create(escopo=self.escopo, cenario=self.cenario, **kwargs)


class AliquotasUfSeedTests(DifalAliquotasUfTestsBase):
    """Tabela oficial (taxgroup 2026) informada no briefing — valores não deduzidos."""

    OFICIAL_2026 = {
        'AC': '19', 'AL': '21.5', 'AM': '20', 'AP': '18', 'BA': '20.5', 'CE': '20',
        'DF': '20', 'ES': '17', 'GO': '19', 'MA': '23', 'MG': '18', 'MS': '17',
        'MT': '17', 'PA': '19', 'PB': '20', 'PE': '20.5', 'PI': '22.5', 'PR': '19.5',
        'RJ': '22', 'RN': '20', 'RO': '19.5', 'RR': '20', 'RS': '17', 'SC': '17',
        'SE': '20', 'SP': '18', 'TO': '20',
    }

    def test_seed_contem_a_tabela_oficial_do_briefing(self):
        self.assertEqual(set(ALICOTAS_ICMS_UF), set(self.OFICIAL_2026))
        self.assertEqual(len(ALICOTAS_ICMS_UF), 27)
        for uf, interna in self.OFICIAL_2026.items():
            self.assertEqual(
                ALICOTAS_ICMS_UF[uf]['interna'],
                Decimal(interna),
                f'alíquota interna oficial de {uf}',
            )
        for uf, dados in ALICOTAS_ICMS_UF.items():
            esperado = Decimal('12') if uf in UF_FAIXA_INTERESTADUAL_12 else Decimal('7')
            self.assertEqual(dados['interestadual'], esperado, f'interestadual de {uf}')

    def test_seed_migra_todas_as_ufs_pactuadas(self):
        no_db = {
            r.uf: (r.aliquota_interna, r.aliquota_interestadual)
            for r in AliquotaIcmsUF.objects.filter(ativo=True)
        }
        self.assertEqual(set(no_db), set(ALICOTAS_ICMS_UF), 'migration 0016/0018 não semeou a tabela')
        for uf, dados in ALICOTAS_ICMS_UF.items():
            interna_db, inter_db = no_db[uf]
            self.assertEqual(interna_db, dados['interna'], f'interna {uf} no banco')
            self.assertEqual(inter_db, dados['interestadual'], f'interestadual {uf} no banco')

    def test_seed_nao_presume_fcp(self):
        com_fcp = list(
            AliquotaIcmsUF.objects.exclude(aliquota_fcp__isnull=True).values_list('uf', flat=True),
        )
        self.assertEqual(com_fcp, [], 'FCP só é emitido com alíquota cadastrada na regra, nunca presumido')

    def test_campos_de_auditoria_da_tabela(self):
        linha = AliquotaIcmsUF.objects.get(uf='SP')
        self.assertIsNone(linha.vigencia_inicio, 'seed não inventa data de vigência')
        self.assertIsNone(linha.atualizado_por_id, 'seed não tem autor humano')
        self.assertIsNotNone(linha.atualizado_em)

    def test_interestadual_12_sul_sudeste_7_demais(self):
        self.assertEqual(interestadual_padrao_para_uf('SP'), Decimal('12'))
        self.assertEqual(interestadual_padrao_para_uf('PR'), Decimal('12'))
        self.assertEqual(interestadual_padrao_para_uf('RS'), Decimal('12'))
        self.assertEqual(interestadual_padrao_para_uf('MG'), Decimal('12'))
        self.assertEqual(interestadual_padrao_para_uf('RJ'), Decimal('12'))
        self.assertEqual(interestadual_padrao_para_uf('BA'), Decimal('7'))

    def test_es_fica_na_faixa_dos_7_porcento(self):
        """Contador (2026-10-29): ES trata como Norte/Nordeste/Centro-Oeste — a taxgroup errava aqui."""
        self.assertEqual(ALICOTAS_ICMS_UF['ES']['interestadual'], Decimal('7'))
        self.assertEqual(interestadual_padrao_para_uf('ES'), Decimal('7'))
        self.assertNotIn('ES', UF_FAIXA_INTERESTADUAL_12)


class ResolverAliquotasDifalTests(DifalAliquotasUfTestsBase):
    def test_sp_uf_destino_usa_tabela_quando_regra_generica(self):
        AliquotaIcmsUF.objects.update_or_create(
            uf='SP',
            defaults={'aliquota_interna': Decimal('18'), 'aliquota_interestadual': Decimal('12'), 'ativo': True},
        )
        resolvida = resolver_aliquotas_difal(self._criar_regra(), uf_destino='SP')
        self.assertEqual(resolvida.pendencias, [])
        self.assertEqual(resolvida.aliquota_interna_destino, Decimal('18'))
        self.assertEqual(resolvida.aliquota_interestadual, Decimal('12'))
        self.assertIn('interna_destino:tabela_uf', resolvida.fontes)

    def test_es_pega_7_da_tabela_semeada_sem_override(self):
        resolvida = resolver_aliquotas_difal(self._criar_regra(), uf_destino='ES')
        self.assertEqual(resolvida.pendencias, [])
        self.assertEqual(resolvida.aliquota_interestadual, Decimal('7'))
        self.assertEqual(resolvida.aliquota_interna_destino, Decimal('17'))
        self.assertEqual(resolvida.fontes, ['interestadual:tabela_uf', 'interna_destino:tabela_uf'])

    def test_override_na_regra_vence_sobre_tabela(self):
        AliquotaIcmsUF.objects.update_or_create(
            uf='BA',
            defaults={'aliquota_interna': Decimal('20.5'), 'aliquota_interestadual': Decimal('7'), 'ativo': True},
        )
        regra = self._criar_regra(
            nome='NCM 8481 override',
            aliquota_icms_interestadual=Decimal('7'),
            aliquota_icms_interna_destino=Decimal('25'),
        )
        resolvida = resolver_aliquotas_difal(regra, uf_destino='BA')
        self.assertEqual(resolvida.aliquota_interna_destino, Decimal('25'))
        self.assertIn('interna_destino:regra', resolvida.fontes)

    def test_uf_fora_da_tabela_sem_override_gera_pendencias(self):
        AliquotaIcmsUF.objects.filter(uf='BA').delete()
        resolvida = resolver_aliquotas_difal(self._criar_regra(), uf_destino='BA', nome_item='Produto X')
        self.assertEqual(len(resolvida.pendencias), 2)
        self.assertIn('alíquota ICMS interestadual', resolvida.pendencias[0])
        self.assertIn('alíquota ICMS interna da UF BA', resolvida.pendencias[1])

    def test_validar_parametros_herda_tabela_e_sem_uf_destino_mantem_mensagem_legada(self):
        regra = self._criar_regra()
        AliquotaIcmsUF.objects.get_or_create(
            uf='PR',
            defaults={'aliquota_interna': Decimal('19.5'), 'aliquota_interestadual': Decimal('12'), 'ativo': True},
        )
        self.assertEqual(validar_parametros_difal_regra(regra, uf_destino='PR'), [])
        erros_sem_uf = validar_parametros_difal_regra(regra)
        self.assertEqual(len(erros_sem_uf), 2)
        self.assertIn('informe alíquota ICMS interestadual para DIFAL.', erros_sem_uf[0])
        self.assertIn('informe alíquota ICMS interna da UF destino para DIFAL.', erros_sem_uf[1])


class DifalFormulaPorUfTests(DifalAliquotasUfTestsBase):
    """DIFAL = Base × (AliqInterna_destino − AliqInterestadual) / 100 — SP, BA, PR."""

    def _criar_uf(self, uf: str, interna: str, inter: str) -> None:
        AliquotaIcmsUF.objects.update_or_create(
            uf=uf,
            defaults={
                'aliquota_interna': Decimal(interna),
                'aliquota_interestadual': Decimal(inter),
                'ativo': True,
            },
        )

    def test_sp_1000_difal_60(self):
        self._criar_uf('SP', '18', '12')
        regra = self._criar_regra()
        difal = calcular_difal_item(
            Decimal('1000.00'), regra, aliquotas=resolver_aliquotas_difal(regra, uf_destino='SP'),
        )
        self.assertEqual(difal['p_icms_uf_dest'], '18.00')
        self.assertEqual(difal['p_icms_inter'], '12.00')
        self.assertEqual(difal['v_icms_uf_dest'], '60.00')
        self.assertEqual(difal['fontes_aliquota'], 'interestadual:tabela_uf,interna_destino:tabela_uf')

    def test_ba_1000_difal_135(self):
        self._criar_uf('BA', '20.5', '7')
        regra = self._criar_regra()
        difal = calcular_difal_item(
            Decimal('1000.00'), regra, aliquotas=resolver_aliquotas_difal(regra, uf_destino='BA'),
        )
        self.assertEqual(difal['p_icms_uf_dest'], '20.50')
        self.assertEqual(difal['p_icms_inter'], '7.00')
        self.assertEqual(difal['v_icms_uf_dest'], '135.00')

    def test_pr_1000_difal_75(self):
        self._criar_uf('PR', '19.5', '12')
        regra = self._criar_regra()
        difal = calcular_difal_item(
            Decimal('1000.00'), regra, aliquotas=resolver_aliquotas_difal(regra, uf_destino='PR'),
        )
        self.assertEqual(difal['p_icms_uf_dest'], '19.50')
        self.assertEqual(difal['p_icms_inter'], '12.00')
        self.assertEqual(difal['v_icms_uf_dest'], '75.00')

    def test_es_1000_difal_100(self):
        """ES 17% interna − 7% interestadual = 10% (não 5%)."""
        self._criar_uf('ES', '17', '7')
        regra = self._criar_regra()
        difal = calcular_difal_item(
            Decimal('1000.00'), regra, aliquotas=resolver_aliquotas_difal(regra, uf_destino='ES'),
        )
        self.assertEqual(difal['p_icms_uf_dest'], '17.00')
        self.assertEqual(difal['p_icms_inter'], '7.00')
        self.assertEqual(difal['v_icms_uf_dest'], '100.00')

    def test_regra_diferente_por_destino_nao_compartilha_base_unica(self):
        self._criar_uf('SP', '18', '12')
        self._criar_uf('BA', '20.5', '7')
        self._criar_uf('PR', '19.5', '12')
        regra = self._criar_regra()
        valores = {}
        for uf in ('SP', 'BA', 'PR'):
            difal = calcular_difal_item(
                Decimal('2000.00'), regra, aliquotas=resolver_aliquotas_difal(regra, uf_destino=uf),
            )
            valores[uf] = difal['v_icms_uf_dest']
        self.assertEqual(valores, {'SP': '120.00', 'BA': '270.00', 'PR': '150.00'})

    def test_sem_aliquotas_resolvidas_mantem_comportamento_legado_da_regra(self):
        regra = self._criar_regra(
            aliquota_icms_interestadual=Decimal('12'),
            aliquota_icms_interna_destino=Decimal('18'),
        )
        difal = calcular_difal_item(Decimal('500.00'), regra)
        self.assertEqual(difal['v_icms_uf_dest'], '30.00')
        self.assertNotIn('fontes_aliquota', difal)


class DifalRetificacaoRegiaoTests(TestCase):
    def test_interestadual_regiao_sp_destinos(self):
        self.assertEqual(interestadual_regiao('SP', 'PR'), Decimal('12'))
        self.assertEqual(interestadual_regiao('SP', 'MG'), Decimal('12'))
        self.assertEqual(interestadual_regiao('SP', 'BA'), Decimal('7'))
        self.assertEqual(interestadual_regiao('SP', 'PE'), Decimal('7'))
        self.assertEqual(interestadual_regiao('SP', 'ES'), Decimal('7'))

    def test_interestadual_regiao_origem_es_ou_demais_usa_12(self):
        self.assertEqual(interestadual_regiao('ES', 'SP'), Decimal('12'))

    def test_interestadual_regiao_origem_fora_do_sul_sudeste_usa_12(self):
        self.assertEqual(interestadual_regiao('BA', 'SP'), Decimal('12'))
        self.assertEqual(interestadual_regiao('MA', 'PR'), Decimal('12'))
        self.assertEqual(interestadual_regiao('GO', 'BA'), Decimal('12'))


@override_settings(USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS=True)
class DifalSemBaseUnicaIntegracaoTests(DifalAliquotasUfTestsBase):
    """Regra genérica única + tabela de UF: o mesmo item para BA/PR/MG/ES gera DIFAL diferentes (400,00)."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user('difal310', 'difal310@test.com', 'x')
        RegraFiscalSaida.objects.create(
            escopo=self.escopo,
            cenario=self.cenario,
            nome='Configuração genérica',
            ativo=True,
            uf_origem='SP',
            uf_destino='',
            cfop_venda='6108',
            cst_icms='00',
            aliquota_icms=Decimal('12'),
            cst_pis='01',
            aliquota_pis=Decimal('1.65'),
            cst_cofins='01',
            aliquota_cofins=Decimal('7.6'),
            difal_aplicavel=True,
            aliquota_icms_interestadual=None,
            aliquota_icms_interna_destino=None,
        )

    def _nf_com_impostos(self, uf_destino: str, *, frete: Decimal | None = None) -> NFeSaida:
        pedido, item = _pedido_item()
        pedido.cliente.uf = uf_destino
        pedido.cliente.save(update_fields=['uf'])
        fat = _faturamento_pronto(pedido, item)
        gerada = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        if frete is not None:
            NFeSaida.objects.filter(pk=gerada['nfe_saida_id']).update(valor_frete=frete)
        nf = NFeSaida.objects.prefetch_related('itens__produto', 'cliente').get(pk=gerada['nfe_saida_id'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user, motivo='Auditoria DIFAL por UF')
        return NFeSaida.objects.prefetch_related('itens__produto', 'cliente').get(pk=nf.pk)

    def _difal_emitido_para(self, uf_destino: str) -> dict[str, str]:
        nf = self._nf_com_impostos(uf_destino)
        nf_item = nf.itens.first()
        assert nf_item is not None
        difal = (nf_item.snapshot_fiscal or {}).get('difal') or {}
        self.assertEqual(difal.get('aplicavel'), True, f'DIFAL não calculado para {uf_destino}')
        return difal

    def test_quatro_destinos_quatro_difais(self):
        esperado = {
            'BA': ('20.50', '7.00', '54.00'),
            'PR': ('19.50', '12.00', '30.00'),
            'MG': ('18.00', '12.00', '24.00'),
            'ES': ('17.00', '7.00', '40.00'),
        }
        observado = {}
        for uf, valores in esperado.items():
            difal = self._difal_emitido_para(uf)
            observado[uf] = (
                difal['p_icms_uf_dest'],
                difal['p_icms_inter'],
                difal['v_icms_uf_dest'],
            )
            self.assertEqual(observado[uf], valores, f'DIFAL incorreto para {uf}')
        self.assertEqual(len({v[2] for v in observado.values()}), 4, 'base única: DIFAL igual entre UFs')

    def test_regra_sem_difal_aplicavel_nao_gera_snapshot(self):
        RegraFiscalSaida.objects.update(difal_aplicavel=False)
        pedido, item = _pedido_item()
        pedido.cliente.uf = 'BA'
        pedido.cliente.save(update_fields=['uf'])
        fat = _faturamento_pronto(pedido, item)
        gerada = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.prefetch_related('itens__produto', 'cliente').get(pk=gerada['nfe_saida_id'])
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user, motivo='Sem DIFAL')
        nf_item = nf.itens.first()
        assert nf_item is not None
        nf_item.refresh_from_db()
        snap = nf_item.snapshot_fiscal or {}
        self.assertNotIn('difal', snap)

    def test_frete_da_nfe_gera_aviso_mas_nao_altera_a_base(self):
        nf = self._nf_com_impostos('BA', frete=Decimal('80.00'))
        item = nf.itens.first()
        assert item is not None
        snap = item.snapshot_fiscal or {}
        self.assertEqual(snap['difal']['v_icms_uf_dest'], '54.00', 'decisão: só sinalizar, BC segue o produto')
        self.assertNotIn('difal_pendencias', snap)
        avisos = snap.get('difal_avisos') or []
        self.assertEqual(len(avisos), 1, snap)
        self.assertIn('frete', avisos[0])
        self.assertIn('R$ 80.00', avisos[0])

    def test_aviso_de_frete_e_alerta_e_nao_aumenta_pendencias(self):
        nf = self._nf_com_impostos('BA', frete=Decimal('80.00'))
        com_aviso = validar_nfe_saida_para_emissao(nf, modo='leve')
        itens = [it for grupo in com_aviso['grupos'].values() for it in grupo]
        alvos = [it for it in itens if it.get('codigo') == 'DIFAL_BC_SEM_FRETE']
        self.assertEqual(len(alvos), 1, com_aviso)
        self.assertEqual(alvos[0]['tipo'], TIPO_ALERTA)

        item = nf.itens.first()
        assert item is not None
        snap = dict(item.snapshot_fiscal or {})
        snap.pop('difal_avisos', None)
        ItemNFeSaida.objects.filter(pk=item.pk).update(snapshot_fiscal=snap)
        sem_aviso = validar_nfe_saida_para_emissao(
            NFeSaida.objects.prefetch_related('itens__produto', 'cliente').get(pk=nf.pk),
            modo='leve',
        )
        itens_sem = [it for grupo in sem_aviso['grupos'].values() for it in grupo]
        self.assertEqual([it for it in itens_sem if it.get('codigo') == 'DIFAL_BC_SEM_FRETE'], [])
        self.assertEqual(sem_aviso['total_pendencias'], com_aviso['total_pendencias'])
        self.assertEqual(sem_aviso['pode_emitir'], com_aviso['pode_emitir'])


class DifalRetificacaoAuditoriaTests(DifalAliquotasUfTestsBase):
    """Comando de auditoria: NF-e emitida com alíquota de SP vendendo para BA aparece como A_MENOR."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user('aud310', 'aud310@test.com', 'x')

    def _nf_ba_com_difal_de_sp(self, *, frete: Decimal | None = None) -> NFeSaida:
        regra = self._criar_regra(
            uf_origem='SP',
            uf_destino='BA',
            aliquota_icms_interestadual=Decimal('12'),
            aliquota_icms_interna_destino=Decimal('18'),
        )
        pedido, item = _pedido_item()
        pedido.cliente.uf = 'BA'
        pedido.cliente.save(update_fields=['uf'])
        fat = _faturamento_pronto(pedido, item)
        gerada = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        if frete is not None:
            NFeSaida.objects.filter(pk=gerada['nfe_saida_id']).update(valor_frete=frete)
        nf = NFeSaida.objects.prefetch_related('itens__produto', 'cliente').get(pk=gerada['nfe_saida_id'])
        with patch(
            'apps.fiscal.nfe_saida_atualizar_impostos.buscar_regra_fiscal_nfe_saida_rascunho',
            return_value=(
                {
                    'origem': 'CENARIO_SAIDA',
                    'regra_id': regra.id,
                    'cfop': '6108',
                    'cst_icms': '00',
                    'aliquota_icms': '12',
                    'aliquota_pis': '1.65',
                    'aliquota_cofins': '7.6',
                },
                regra,
                {},
            ),
        ):
            aplicar_atualizacao_impostos_nfe(nf, usuario=self.user, motivo='Base única (SP aplicada a BA)')
        nf.ambiente_emissao = NFeSaida.AmbienteEmissao.PRODUCAO
        nf.status = 'AUTORIZADA'
        nf.save(update_fields=['ambiente_emissao', 'status'])
        return nf

    def test_auditoria_aponta_difal_a_menor_e_totaliza(self):
        nf = self._nf_ba_com_difal_de_sp()
        nf.refresh_from_db()
        rel = analisar_difal_retificacao(desde=None, uf_exclusao_origem=None)
        self.assertEqual(rel.nf_avaliadas, 1)
        divergentes = [linha for linha in rel.linhas if linha.divergente]
        self.assertEqual(len(divergentes), 1, formatar_relatorio_difal_retificacao(rel))
        linha = divergentes[0]
        self.assertEqual(linha.uf_destino, 'BA')
        self.assertEqual(linha.p_emitido, Decimal('18'))
        self.assertEqual(linha.p_correto, Decimal('20.5'))
        self.assertEqual(linha.v_emitido, Decimal('24.00'))
        self.assertEqual(linha.v_correto, Decimal('54.00'))
        self.assertEqual(linha.diferenca, Decimal('30.00'))
        self.assertEqual(linha.situacao, 'A_MENOR')
        self.assertEqual(rel.total_diferenca, Decimal('30.00'))
        self.assertIn('A_MENOR', formatar_relatorio_difal_retificacao(rel))

    def test_auditoria_marca_item_com_frete_fora_da_base(self):
        self._nf_ba_com_difal_de_sp(frete=Decimal('80.00'))
        rel = analisar_difal_retificacao(desde=None, uf_exclusao_origem=None)
        self.assertEqual(rel.itens_com_frete_fora_da_base, 1)
        self.assertTrue(all(linha.frete_sem_base for linha in rel.linhas))
        texto = formatar_relatorio_difal_retificacao(rel)
        self.assertIn('FRETE FORA DA BASE', texto)
        self.assertIn('subestimado', texto)

    def test_auditoria_sem_frete_nao_sinaliza_base(self):
        self._nf_ba_com_difal_de_sp()
        rel = analisar_difal_retificacao(desde=None, uf_exclusao_origem=None)
        self.assertEqual(rel.itens_com_frete_fora_da_base, 0)
        self.assertNotIn('FRETE FORA DA BASE', formatar_relatorio_difal_retificacao(rel))
