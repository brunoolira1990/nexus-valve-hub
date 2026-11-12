"""FASE 1 — DIFAL alínea "b": local de entrada física diferente do destinatário.

Cobre a resolução jurídica do destino (função pura), o método de base por UF,
o snapshot/XML do cenário real (BA cadastral × ES entrega), o gate de emissão e
a regressão byte a byte para operações sem grupo entrega e internas.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import re
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_destinatario_fiscal import (
    PerfilDestinatarioFiscal,
    resolver_perfil_destinatario_nf,
)
from apps.fiscal.nfe_difal_calculo import determinar_metodo_base_difal
from apps.fiscal.nfe_difal_destino import (
    ALINEA_A,
    ALINEA_B,
    ORIGEM_BLOQUEADO,
    ORIGEM_CADASTRO,
    ORIGEM_ENTREGA,
    resolver_destino_tributario,
)
from apps.fiscal.nfe_saida_atualizar_impostos import aplicar_atualizacao_impostos_nfe
from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
from apps.fiscal.nfe_saida_from_faturamento import gerar_nfe_saida_from_faturamento
from apps.fiscal.nfe_saida_preview import gerar_preview_xml_nfe_saida
from apps.fiscal.tests.test_nfe_saida_faturamento import _faturamento_pronto, _pedido_item
from apps.fiscal.validacao_nfe_saida import _validar_difal_local_entrega
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import (
    AliquotaIcmsUF,
    CenarioFiscalSaidaEscopo,
    RegraFiscalSaida,
)


def _perfil(*, contribuinte: bool, consumidor_final: bool = True) -> PerfilDestinatarioFiscal:
    return PerfilDestinatarioFiscal(
        destinatario_contribuinte=(
            RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE
            if contribuinte
            else RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE
        ),
        ind_ie_dest='1' if contribuinte else '9',
        consumidor_final=consumidor_final,
    )


def _nf(
    uf_cadastral: str = 'BA',
    *,
    entrega_uf: str = '',
    confirmado: bool = False,
    completo: bool = True,
):
    return SimpleNamespace(
        cliente=SimpleNamespace(uf=uf_cadastral),
        cliente_id=1,
        pedido_venda=None,
        entrega_UF=entrega_uf,
        entrega_cUF='32' if completo and entrega_uf else '',
        entrega_cMun='3205309' if completo and entrega_uf else '',
        entrega_xLgr='Rua da Entrada' if completo and entrega_uf else '',
        difal_endereco_entrada_fisica_confirmado=confirmado,
    )


class ResolverDestinoTributarioTests(SimpleTestCase):
    """Cenários 1–9 do item 10 da spec (A1: alínea b, não contribuinte)."""

    def test_cenario_1_entrega_igual_ao_cadastro(self):
        r = resolver_destino_tributario(
            _nf('BA', entrega_uf='BA'),
            _perfil(contribuinte=False),
            uf_cadastral='BA',
        )
        self.assertEqual(r.uf, 'BA')
        self.assertEqual(r.fundamento, ALINEA_B)
        self.assertEqual(r.origem, ORIGEM_CADASTRO)
        self.assertFalse(r.bloqueado)

    def test_cenario_2_entrega_es_diverge_da_ba_confirmada(self):
        r = resolver_destino_tributario(
            _nf('BA', entrega_uf='ES', confirmado=True),
            _perfil(contribuinte=False),
            uf_cadastral='BA',
        )
        self.assertEqual(r.uf, 'ES')
        self.assertEqual(r.fundamento, ALINEA_B)
        self.assertEqual(r.origem, ORIGEM_ENTREGA)
        self.assertTrue(r.confirmado)
        self.assertFalse(r.bloqueado)
        self.assertEqual(r.pendencias, ())
        # R3: as três UFs permanecem independentes e visíveis.
        self.assertEqual(r.uf_cadastral, 'BA')
        self.assertEqual(r.uf_entrega, 'ES')

    def test_cenario_3_entrega_rj_diverge_de_mg_confirmada(self):
        r = resolver_destino_tributario(
            _nf('MG', entrega_uf='RJ', confirmado=True),
            _perfil(contribuinte=False),
            uf_cadastral='MG',
        )
        self.assertEqual(r.uf, 'RJ')
        self.assertEqual(r.origem, ORIGEM_ENTREGA)

    def test_cenario_4_sem_entrega_usa_cadastro(self):
        r = resolver_destino_tributario(
            _nf('ES'),
            _perfil(contribuinte=False),
            uf_cadastral='ES',
        )
        self.assertEqual(r.uf, 'ES')
        self.assertEqual(r.origem, ORIGEM_CADASTRO)

    def test_cenario_5_contribuinte_fica_bloqueado_para_fase_1_1(self):
        r = resolver_destino_tributario(
            _nf('BA', entrega_uf='ES', confirmado=True),
            _perfil(contribuinte=True, consumidor_final=False),
            uf_cadastral='BA',
        )
        self.assertTrue(r.bloqueado)
        self.assertEqual(r.fundamento, ALINEA_A)
        self.assertEqual(r.origem, ORIGEM_BLOQUEADO)
        self.assertTrue(any('FASE 1.1' in p for p in r.pendencias))

    def test_cenario_6_operacao_interna_nao_aplica(self):
        r = resolver_destino_tributario(
            _nf('SP'),
            _perfil(contribuinte=False),
            uf_cadastral='SP',
        )
        self.assertEqual(r.uf, 'SP')
        self.assertEqual(r.origem, ORIGEM_CADASTRO)
        self.assertFalse(r.bloqueado)

    def test_cenario_7_entrega_igual_cadastro_permanece_cadastro(self):
        r = resolver_destino_tributario(
            _nf('PR', entrega_uf='PR', confirmado=True),
            _perfil(contribuinte=False),
            uf_cadastral='PR',
        )
        self.assertEqual(r.uf, 'PR')
        self.assertEqual(r.origem, ORIGEM_CADASTRO)

    def test_cenario_8_grupo_entrega_ausente(self):
        r = resolver_destino_tributario(
            _nf('BA'),
            _perfil(contribuinte=False),
            uf_cadastral='BA',
        )
        self.assertEqual(r.uf, 'BA')
        self.assertEqual(r.origem, ORIGEM_CADASTRO)
        self.assertFalse(r.bloqueado)

    def test_cenario_9_divergente_sem_confirmacao_bloqueia(self):
        r = resolver_destino_tributario(
            _nf('BA', entrega_uf='ES', confirmado=False),
            _perfil(contribuinte=False),
            uf_cadastral='BA',
        )
        self.assertTrue(r.bloqueado)
        self.assertEqual(r.origem, ORIGEM_BLOQUEADO)
        self.assertTrue(any('confirma' in p.lower() for p in r.pendencias))

    def test_cenario_9_confirmada_com_endereco_incompleto_bloqueia(self):
        r = resolver_destino_tributario(
            _nf('BA', entrega_uf='ES', confirmado=True, completo=False),
            _perfil(contribuinte=False),
            uf_cadastral='BA',
        )
        self.assertTrue(r.bloqueado)
        self.assertTrue(any('incompleto' in p.lower() for p in r.pendencias))

    def test_nao_contribuinte_sem_consumidor_final_nao_aplica_difal(self):
        r = resolver_destino_tributario(
            _nf('BA', entrega_uf='ES', confirmado=True),
            _perfil(contribuinte=False, consumidor_final=False),
            uf_cadastral='BA',
        )
        self.assertEqual(r.uf, 'BA')
        self.assertEqual(r.origem, ORIGEM_CADASTRO)
        self.assertFalse(r.bloqueado)


class MetodoBaseDifalTests(TestCase):
    """Cenário 10 (vigência) + método por UF resolvida (BA dupla, ES única, sem linha)."""

    def test_ba_usa_base_dupla(self):
        m = determinar_metodo_base_difal('BA', date.today())
        self.assertTrue(m.usa_base_dupla)
        self.assertEqual(m.memoria['fonte'], 'tabela_aliquota_uf')
        self.assertEqual(m.pendencias, ())

    def test_es_usa_base_unica(self):
        m = determinar_metodo_base_difal('ES', date.today())
        self.assertFalse(m.usa_base_dupla)
        self.assertEqual(m.pendencias, ())

    def test_uf_sem_linha_bloqueia_sem_fallback_geografico(self):
        m = determinar_metodo_base_difal('ZZ', date.today())
        self.assertIsNone(m.usa_base_dupla)
        self.assertTrue(m.pendencias)

    def test_vigencia_futura_nao_e_usada(self):
        AliquotaIcmsUF.objects.create(
            uf='ZY',
            aliquota_interna=Decimal('20'),
            aliquota_interestadual=Decimal('7'),
            usa_base_dupla=False,
            vigencia_inicio=date.today() + timedelta(days=30),
            ativo=True,
        )
        m = determinar_metodo_base_difal('ZY', date.today())
        self.assertIsNone(m.usa_base_dupla)
        self.assertTrue(m.pendencias)

    def test_vigencia_passada_e_usada(self):
        AliquotaIcmsUF.objects.create(
            uf='ZX',
            aliquota_interna=Decimal('18'),
            aliquota_interestadual=Decimal('7'),
            usa_base_dupla=True,
            vigencia_inicio=date(2020, 1, 1),
            ativo=True,
        )
        m = determinar_metodo_base_difal('ZX', date.today())
        self.assertTrue(m.usa_base_dupla)
        self.assertEqual(m.vigencia_usada, date(2020, 1, 1))


# Endereço do cliente por UF: o gate de endereço fiscal (pré-existente) confere
# CEP/cidade contra a UF. A consulta externa (ViaCEP) é substituída por este
# mapa determinístico para não depender de rede no teste.
_ENDERECO_POR_UF = {
    'BA': ('Salvador', '40010-000'),
    'SP': ('São Paulo', '01001-000'),
    'RJ': ('Rio de Janeiro', '20040-020'),
    'ES': ('Vitória', '29010-000'),
}
_CEP_PARA_LOCALIDADE = {
    '40010000': {'uf': 'BA', 'cidade': 'Salvador'},
    '01001000': {'uf': 'SP', 'cidade': 'São Paulo'},
    '20040020': {'uf': 'RJ', 'cidade': 'Rio de Janeiro'},
    '29010000': {'uf': 'ES', 'cidade': 'Vitória'},
}


class _BaseRegrasEntrega(TestCase):
    def setUp(self):
        patcher = mock.patch(
            'apps.cadastros.endereco_fiscal.consultar_cep_viacep',
            side_effect=lambda cep: _CEP_PARA_LOCALIDADE.get(cep or ''),
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.cenario = garantir_cenario_saida_padrao()
        self.escopo = CenarioFiscalSaidaEscopo.objects.get_or_create(
            cenario=self.cenario,
            tipo_escopo=CenarioFiscalSaidaEscopo.TipoEscopo.GERAL,
            defaults={'ativo': True},
        )[0]
        self.user = get_user_model().objects.create_user('difal_entrega', 'difal@test.com', 'x')

    def _criar_regra(self, **kwargs) -> RegraFiscalSaida:
        kwargs.setdefault('escopo', self.escopo)
        kwargs.setdefault('cenario', self.cenario)
        kwargs.setdefault('ativo', True)
        kwargs.setdefault('cfop_venda', '6108')
        kwargs.setdefault('cst_icms', '00')
        kwargs.setdefault('aliquota_icms', Decimal('7'))
        kwargs.setdefault('cst_pis', '01')
        kwargs.setdefault('aliquota_pis', Decimal('1.65'))
        kwargs.setdefault('cst_cofins', '01')
        kwargs.setdefault('aliquota_cofins', Decimal('7.6'))
        return RegraFiscalSaida.objects.create(**kwargs)

    def _nf_com_entrega(
        self,
        *,
        uf_cadastral: str,
        entrega_uf: str = '',
        confirmado: bool = False,
    ) -> NFeSaida:
        pedido, item = _pedido_item()
        cidade, cep = _ENDERECO_POR_UF[uf_cadastral]
        pedido.cliente.uf = uf_cadastral
        pedido.cliente.cidade = cidade
        pedido.cliente.cep = cep
        pedido.cliente.save(update_fields=['uf', 'cidade', 'cep'])
        fat = _faturamento_pronto(pedido, item)
        gerada = gerar_nfe_saida_from_faturamento(pedido, fat.pk)
        nf = NFeSaida.objects.get(pk=gerada['nfe_saida_id'])
        nf.entrega_UF = entrega_uf or None
        if entrega_uf:
            nf.entrega_cUF = '32' if entrega_uf == 'ES' else '33'
            nf.entrega_cMun = '3205309' if entrega_uf == 'ES' else '3304557'
            nf.entrega_xMun = 'Vitória' if entrega_uf == 'ES' else 'Rio de Janeiro'
            nf.entrega_xLgr = 'Rua da Entrada'
            nf.entrega_nro = '100'
            nf.entrega_xBairro = 'Centro'
            nf.entrega_CEP = '29010000' if entrega_uf == 'ES' else '20040020'
            nf.entrega_cnpj = '12345678000199'
        nf.difal_endereco_entrada_fisica_confirmado = confirmado
        nf.save()
        return nf

    def _aplicar(self, nf: NFeSaida) -> NFeSaida:
        aplicar_atualizacao_impostos_nfe(nf, usuario=self.user, motivo='Teste DIFAL entrega')
        return NFeSaida.objects.prefetch_related('itens__produto', 'cliente').get(pk=nf.pk)


class DifalEntregaIntegracaoTests(_BaseRegrasEntrega):
    """Cenário real: cliente BA, entrega ES, regra SP->ES habilitada (D1)."""

    def setUp(self):
        super().setUp()
        # Regra cadastral genérica: alimenta ICMS/CFOP do item (SP -> qualquer UF).
        self._criar_regra(
            nome='Genérica SP',
            uf_origem='SP',
            uf_destino='',
            difal_aplicavel=False,
        )
        # Regra da UF resolvida: só o DIFAL (SP -> ES), alíquotas do seed.
        self.regra_es = self._criar_regra(
            nome='SP -> ES DIFAL',
            uf_origem='SP',
            uf_destino='ES',
            difal_aplicavel=True,
            aliquota_icms_interestadual=Decimal('7'),
            aliquota_icms_interna_destino=Decimal('17'),
        )

    def test_snapshot_usa_uf_de_entrega_e_memoria_de_calculo(self):
        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='BA', entrega_uf='ES', confirmado=True))
        item = nf.itens.first()
        assert item is not None
        snap = item.snapshot_fiscal or {}
        difal = snap.get('difal') or {}

        self.assertTrue(difal.get('aplicavel'))
        self.assertEqual(difal.get('tipo_base'), 'UNICA')
        self.assertEqual(difal.get('p_icms_uf_dest'), '17.00')
        self.assertEqual(difal.get('p_icms_inter'), '7.00')
        self.assertEqual(difal.get('v_icms_uf_dest'), '40.00')
        self.assertEqual(difal.get('p_icms_inter_part'), '100.00')
        self.assertEqual(difal.get('v_icms_uf_remet'), '0.00')
        # Memória A4 (UF eleita, fundamento, origem, base, vigência, FCP).
        self.assertEqual(difal.get('uf_destino'), 'ES')
        self.assertEqual(difal.get('fundamento'), ALINEA_B)
        self.assertEqual(difal.get('origem_resolucao'), ORIGEM_ENTREGA)
        self.assertEqual(difal.get('uf_cadastral'), 'BA')
        self.assertEqual(difal.get('uf_entrega'), 'ES')
        self.assertTrue(difal.get('confirmado_local_entrada_fisica'))
        self.assertFalse(difal.get('usa_base_dupla'))
        self.assertIn('fcp_pendente', difal)
        self.assertEqual(snap.get('difal_resolucao', {}).get('uf'), 'ES')

        # Auditoria na NF: UF eleita, fundamento e origem; cadastro intocado (R3).
        self.assertEqual(nf.difal_uf_destino, 'ES')
        self.assertEqual(nf.difal_fundamento, ALINEA_B)
        self.assertEqual(nf.difal_origem_resolucao, ORIGEM_ENTREGA)
        self.assertEqual(nf.cliente.uf, 'BA')
        self.assertEqual(nf.entrega_UF, 'ES')

    def test_xml_emite_icmsufdest_da_uf_de_entrega_e_memoria_no_infcpl(self):
        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='BA', entrega_uf='ES', confirmado=True))
        dados = gerar_preview_xml_nfe_saida(nf)
        self.assertFalse(dados.get('bloqueado'), dados.get('mensagens'))
        xml = dados['xml']
        # Remove prefixos de namespace para comparar a estrutura do grupo.
        xml_limpo = re.sub(r'<(/?)(?:[\w.-]+:)?', r'<\1', xml)

        self.assertIn('<ICMSUFDest>', xml_limpo)
        self.assertIn('<vICMSUFDest>40.00</vICMSUFDest>', xml_limpo)
        self.assertIn('<pICMSUFDest>17.0000</pICMSUFDest>', xml_limpo)
        self.assertIn('<pICMSInter>7.00</pICMSInter>', xml_limpo)
        self.assertIn('<vICMSUFRemet>0.00</vICMSUFRemet>', xml_limpo)
        # Destinatário jurídico continua BA; entrega em ES aparece no grupo <entrega>.
        self.assertIn('<UF>BA</UF>', xml_limpo)
        self.assertIn('<UF>ES</UF>', xml_limpo)
        # Memória de cálculo A4 no infCpl (por item + total; texto normalizado em caixa alta).
        inf_cpl = re.search(r'<infCpl>(.*?)</infCpl>', xml_limpo, re.S)
        assert inf_cpl is not None
        texto = inf_cpl.group(1)
        self.assertIn('DIFAL ITEM 1: DESTINO ES', texto)
        self.assertIn('LC 87/96 ART. 11, V, "B"', texto)
        self.assertIn('BASE UNICA', texto)
        self.assertIn('DIFAL TOTAL', texto)

    def test_xml_oficial_cenario_2_valida_xsd_so_signature(self):
        """XML de emissão (<NFe>) do cenário 2: XSD só pode acusar Signature ausente."""
        from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe
        from apps.fiscal.nfe_emissao.schema_validacao import validar_xml_nfe_schema
        from apps.fiscal.nfe_emissao.xml_oficial import gerar_xml_oficial_emissao
        from apps.fiscal.nfe_saida_prontidao import marcar_nfe_pronta_para_emissao

        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='BA', entrega_uf='ES', confirmado=True))
        from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe

        empresa = nf.pedido_venda.empresa_emitente
        empresa.ie = '123456789012'
        empresa.logradouro = 'Rua do Emitente'
        empresa.numero = '100'
        empresa.bairro = 'Centro'
        empresa.cidade = 'São Paulo'
        empresa.cep = '01001000'
        empresa.save(update_fields=['ie', 'logradouro', 'numero', 'bairro', 'cidade', 'cep'])
        ensure_numeracao_padrao_nfe(empresa)
        nf.ind_final = '1'
        nf.ind_pres = '1'
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['ind_final', 'ind_pres', 'indicadores_fiscais_confirmados'])
        marcar_nfe_pronta_para_emissao(nf, usuario=self.user)
        reservar_numeracao_nfe(nf, ambiente=NFeSaida.AmbienteEmissao.HOMOLOGACAO, usuario=self.user)
        nf.refresh_from_db()
        nf.indicadores_fiscais_confirmados = True
        nf.save(update_fields=['indicadores_fiscais_confirmados'])

        xml = gerar_xml_oficial_emissao(nf).decode('utf-8')
        self.assertIn('<ICMSUFDest>', xml)
        self.assertIn('<vICMSUFDest>40.00</vICMSUFDest>', xml)
        self.assertIn('<UF>ES</UF>', xml)

        res = validar_xml_nfe_schema(xml, 'NFE')
        nao_assinatura = [
            e for e in res['erros']
            if 'Signature' not in f"{e.get('elemento', '')} {e.get('mensagem', '')}"
        ]
        self.assertEqual(nao_assinatura, [])

    def test_conferencia_expoe_bloco_difal(self):
        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='BA', entrega_uf='ES', confirmado=True))
        payload = montar_conferencia_nfe_saida(nf, incluir_checklist=False)
        difal = payload['difal']
        self.assertEqual(difal['uf_origem'], 'SP')
        self.assertEqual(difal['uf_destinatario'], 'BA')
        self.assertEqual(difal['uf_entrega'], 'ES')
        self.assertEqual(difal['uf_destino'], 'ES')
        self.assertEqual(difal['fundamento'], ALINEA_B)
        self.assertEqual(difal['origem_resolucao'], ORIGEM_ENTREGA)
        self.assertTrue(difal['aplicavel'])
        self.assertEqual(difal['totais'].get('v_icms_uf_dest'), '40.00')
        self.assertTrue(difal['itens'])

    def test_gate_bloqueia_divergencia_sem_confirmacao(self):
        nf = self._nf_com_entrega(uf_cadastral='BA', entrega_uf='ES', confirmado=False)
        nf = self._aplicar(nf)
        item = nf.itens.first()
        assert item is not None
        grupos: dict = {}
        _validar_difal_local_entrega(
            grupos,
            nf=nf,
            perfil_nf=resolver_perfil_destinatario_nf(nf),
            rotulo='Item 1',
            item_id=item.pk,
            regra_snapshot_id=None,
        )
        codigos = [e['codigo'] for e in grupos.get('fiscal', [])]
        self.assertIn('DIFAL_LOCAL_ENTREGA_BLOQUEADO', codigos)
        # Sem confirmação não há DIFAL calculado (não presume nada — R6).
        self.assertFalse((item.snapshot_fiscal or {}).get('difal'))

    def test_gate_libera_confirmado_e_bloqueia_fcp_sem_aliquota(self):
        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='BA', entrega_uf='ES', confirmado=True))
        item = nf.itens.first()
        assert item is not None
        grupos: dict = {}
        _validar_difal_local_entrega(
            grupos,
            nf=nf,
            perfil_nf=resolver_perfil_destinatario_nf(nf),
            rotulo='Item 1',
            item_id=item.pk,
            regra_snapshot_id=self.regra_es.pk,
        )
        codigos = [e['codigo'] for e in grupos.get('fiscal', [])]
        self.assertNotIn('DIFAL_LOCAL_ENTREGA_BLOQUEADO', codigos)

        self.regra_es.fcp_aplicavel = True
        self.regra_es.aliquota_fcp = None
        self.regra_es.save(update_fields=['fcp_aplicavel', 'aliquota_fcp'])
        grupos_fcp: dict = {}
        _validar_difal_local_entrega(
            grupos_fcp,
            nf=nf,
            perfil_nf=resolver_perfil_destinatario_nf(nf),
            rotulo='Item 1',
            item_id=item.pk,
            regra_snapshot_id=self.regra_es.pk,
        )
        codigos_fcp = [e['codigo'] for e in grupos_fcp.get('fiscal', [])]
        self.assertIn('DIFAL_FCP_SEM_ALIQUOTA', codigos_fcp)


class DifalEntregaRegressaoTests(_BaseRegrasEntrega):
    """R7: operações sem grupo entrega e internas não mudam."""

    def setUp(self):
        super().setUp()
        self._criar_regra(
            nome='Genérica SP',
            uf_origem='SP',
            uf_destino='',
            difal_aplicavel=True,
        )

    def test_sem_grupo_entrega_mantem_difal_cadastral_e_sem_memoria(self):
        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='BA'))
        item = nf.itens.first()
        assert item is not None
        snap = item.snapshot_fiscal or {}
        difal = snap.get('difal') or {}
        # Mesmo número do baseline BA (base única 20,5/7 sobre BC 400).
        self.assertEqual(difal.get('v_icms_uf_dest'), '67.92')
        # Nenhuma chave de memória de entrega é adicionada ao snapshot.
        self.assertNotIn('uf_destino', difal)
        self.assertNotIn('difal_resolucao', snap)
        self.assertEqual(nf.difal_uf_destino, 'BA')
        self.assertEqual(nf.difal_origem_resolucao, ORIGEM_CADASTRO)

    def test_operacao_interna_nao_gera_difal(self):
        nf = self._aplicar(self._nf_com_entrega(uf_cadastral='SP'))
        item = nf.itens.first()
        assert item is not None
        snap = item.snapshot_fiscal or {}
        self.assertNotIn('difal', snap)
        self.assertNotIn('difal_resolucao', snap)
