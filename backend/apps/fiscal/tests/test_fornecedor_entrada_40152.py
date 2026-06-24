"""ERP 4.0.15.2.31 — Identificação/vínculo de fornecedor em NF-e e CT-e de entrada."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Fornecedor
from apps.cadastros.utils import validar_cnpj
from apps.fiscal.fornecedor_entrada import (
    MSG_FORNECEDOR_DUPLICIDADE,
    StatusIdentificacaoFornecedor,
    buscar_fornecedores_por_cnpj,
    cadastrar_ou_vincular_fornecedor_nfe_entrada,
    identificar_fornecedor_por_party,
    tentar_vincular_fornecedor_nfe_entrada,
    vincular_fornecedor_nfe_entrada,
)
from apps.fiscal.models import CTeHistoricoImportado, NFeEntradaConferencia, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_entrada_financeiro import (
    MSG_SEM_FORNECEDOR,
    montar_flags_financeiro_nfe_entrada,
    preview_contas_pagar_de_nfe_entrada,
)


def _cnpj_valido() -> str:
    for _ in range(40):
        base = f'{uuid.uuid4().int % 10_000_000_000_000:012d}'
        if base == base[0] * 12:
            continue
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        d1 = sum(int(base[i]) * pesos1[i] for i in range(12))
        d1 = 0 if d1 % 11 < 2 else 11 - (d1 % 11)
        parcial = base + str(d1)
        d2 = sum(int(parcial[i]) * pesos2[i] for i in range(13))
        d2 = 0 if d2 % 11 < 2 else 11 - (d2 % 11)
        cnpj = f'{base}{d1}{d2}'
        if validar_cnpj(cnpj):
            return (
                f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}'
            )
    return '03.476.382/0001-00'


CNPJ_CONEFER_MASK = _cnpj_valido()
CNPJ_CONEFER = ''.join(c for c in CNPJ_CONEFER_MASK if c.isdigit())


def _cnpj_alt() -> str:
    h = int(uuid.uuid4().hex[:12], 16)
    return f'{h % 90 + 10:02d}.{h // 100 % 900 + 100:03d}.{h // 100000 % 900 + 100:03d}/0001-{h % 97:02d}'


def _nf_sem_fornecedor(*, cnpj_xml: str = CNPJ_CONEFER) -> NFeEntradaHistoricaImportada:
    return NFeEntradaHistoricaImportada.objects.create(
        chave_acesso=f'35{uuid.uuid4().hex[:42]}'[:44].ljust(44, '0'),
        numero='36425',
        serie='1',
        modelo='55',
        dh_emissao=timezone.make_aware(datetime(2026, 3, 1, 10, 0)),
        valor_total_nf=Decimal('1500.00'),
        cstat='100',
        emit_json={
            'CNPJ': cnpj_xml,
            'xNome': 'CONEFER CONEXOES HID. IMP. EXP. LTDA',
            'IE': '1234567890',
            'enderEmit': {
                'xLgr': 'RUA TESTE',
                'nro': '100',
                'xBairro': 'CENTRO',
                'xMun': 'SAO PAULO',
                'UF': 'SP',
                'CEP': '01001000',
            },
        },
    )


class FornecedorEntradaIdentificacaoTests(TestCase):
    def test_busca_cnpj_normalizado_com_mascara(self):
        forn = Fornecedor.objects.create(
            razao_social='CONEFER',
            cnpj=CNPJ_CONEFER_MASK,
            ativo=True,
        )
        encontrados = buscar_fornecedores_por_cnpj(CNPJ_CONEFER, apenas_ativos=True)
        self.assertEqual([f.id for f in encontrados], [forn.id])

    def test_identifica_fornecedor_unico_ativo(self):
        forn = Fornecedor.objects.create(razao_social='CONEFER', cnpj=CNPJ_CONEFER, ativo=True)
        resultado = identificar_fornecedor_por_party({'CNPJ': CNPJ_CONEFER_MASK, 'xNome': 'CONEFER'})
        self.assertEqual(resultado.status, StatusIdentificacaoFornecedor.ENCONTRADO_UNICO)
        self.assertEqual(resultado.fornecedor_id, forn.id)

    def test_duplicidade_cnpj_bloqueia_auto_vinculo(self):
        Fornecedor.objects.create(razao_social='A', cnpj=CNPJ_CONEFER, ativo=True)
        Fornecedor.objects.create(razao_social='B', cnpj=CNPJ_CONEFER_MASK, ativo=True)
        nf = _nf_sem_fornecedor()
        resultado = tentar_vincular_fornecedor_nfe_entrada(nf, persistir=True)
        self.assertEqual(resultado.status, StatusIdentificacaoFornecedor.DUPLICIDADE)
        nf.refresh_from_db()
        self.assertIsNone(nf.fornecedor_emitente_id)

    def test_auto_vincula_fornecedor_existente_na_conferencia(self):
        forn = Fornecedor.objects.create(razao_social='CONEFER', cnpj=CNPJ_CONEFER_MASK, ativo=True)
        nf = _nf_sem_fornecedor()
        NFeEntradaConferencia.objects.create(nf_entrada_historica=nf, status=NFeEntradaConferencia.Status.PENDENTE)

        resultado = tentar_vincular_fornecedor_nfe_entrada(nf, persistir=True)
        self.assertEqual(resultado.status, StatusIdentificacaoFornecedor.VINCULADO)
        self.assertTrue(resultado.vinculo_automatico)
        nf.refresh_from_db()
        self.assertEqual(nf.fornecedor_emitente_id, forn.id)

    def test_liberar_contas_pagar_apos_auto_vinculo(self):
        Fornecedor.objects.create(razao_social='CONEFER', cnpj=CNPJ_CONEFER, ativo=True)
        nf = _nf_sem_fornecedor()
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf, status=NFeEntradaConferencia.Status.PENDENTE)
        flags = montar_flags_financeiro_nfe_entrada(nf, conf)
        self.assertTrue(flags['pode_gerar_contas_pagar'])
        self.assertNotIn(MSG_SEM_FORNECEDOR, flags['motivo_bloqueio_financeiro'])
        preview = preview_contas_pagar_de_nfe_entrada(nf)
        self.assertTrue(preview['pode_gerar_contas_pagar'])

    def test_fornecedor_inexistente_indica_cadastro(self):
        nf = _nf_sem_fornecedor()
        resultado = identificar_fornecedor_por_party(nf.emit_json)
        self.assertEqual(resultado.status, StatusIdentificacaoFornecedor.NAO_ENCONTRADO)
        flags = montar_flags_financeiro_nfe_entrada(nf)
        self.assertFalse(flags['pode_gerar_contas_pagar'])
        self.assertIn(MSG_SEM_FORNECEDOR, flags['motivo_bloqueio_financeiro'])

    def test_cadastro_rapido_nao_duplica_cnpj(self):
        forn = Fornecedor.objects.create(razao_social='CONEFER', cnpj=CNPJ_CONEFER_MASK, ativo=True)
        nf = _nf_sem_fornecedor()
        retorno, criado, nf = cadastrar_ou_vincular_fornecedor_nfe_entrada(nf, {'razao_social': 'Outro nome'})
        self.assertFalse(criado)
        self.assertEqual(retorno.id, forn.id)
        self.assertEqual(nf.fornecedor_emitente_id, forn.id)

    def test_vincular_manual_por_id(self):
        forn = Fornecedor.objects.create(razao_social='CONEFER', cnpj=CNPJ_CONEFER, ativo=True)
        nf = _nf_sem_fornecedor()
        vincular_fornecedor_nfe_entrada(nf, forn.id)
        nf.refresh_from_db()
        self.assertEqual(nf.fornecedor_emitente_id, forn.id)


class FornecedorEntradaApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('fe40152', 'fe40152@test.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.forn = Fornecedor.objects.create(razao_social='CONEFER', cnpj=CNPJ_CONEFER_MASK, ativo=True)
        self.nf = _nf_sem_fornecedor()
        self.conf = NFeEntradaConferencia.objects.create(
            nf_entrada_historica=self.nf,
            status=NFeEntradaConferencia.Status.PENDENTE,
        )

    def test_conferencia_api_auto_identifica_fornecedor(self):
        res = self.client.get(f'/api/nf-entradas-historicas-importadas/{self.nf.pk}/conferencia/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['fornecedor_id'], self.forn.id)
        self.assertTrue(data['financeiro']['pode_gerar_contas_pagar'])

    def test_cadastrar_vincular_endpoint(self):
        cnpj_novo = _cnpj_valido()
        cnpj_digits = ''.join(c for c in cnpj_novo if c.isdigit())
        nf2 = _nf_sem_fornecedor(cnpj_xml=cnpj_digits)
        NFeEntradaConferencia.objects.create(nf_entrada_historica=nf2, status=NFeEntradaConferencia.Status.PENDENTE)
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{nf2.pk}/fornecedor/cadastrar-vincular/',
            {'razao_social': 'Fornecedor Novo', 'cnpj': cnpj_novo, 'uf': 'SP'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        nf2.refresh_from_db()
        self.assertIsNotNone(nf2.fornecedor_emitente_id)
        self.assertTrue(res.json()['conferencia']['financeiro']['pode_gerar_contas_pagar'])

    def test_vincular_endpoint(self):
        Fornecedor.objects.create(razao_social='Dup', cnpj=CNPJ_CONEFER, ativo=True)
        nf = _nf_sem_fornecedor()
        res = self.client.post(
            f'/api/nf-entradas-historicas-importadas/{nf.pk}/fornecedor/vincular/',
            {'fornecedor_id': self.forn.id},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        nf.refresh_from_db()
        self.assertEqual(nf.fornecedor_emitente_id, self.forn.id)

    def test_cte_auto_identifica_remetente(self):
        cte = CTeHistoricoImportado.objects.create(
            chave_acesso=f'35{uuid.uuid4().hex[:42]}'[:44].ljust(44, '0'),
            numero='100',
            serie='1',
            dh_emissao=timezone.make_aware(datetime(2026, 3, 1, 10, 0)),
            valor_total_servico=Decimal('200.00'),
            rem_json={'CNPJ': CNPJ_CONEFER, 'xNome': 'CONEFER'},
        )
        res = self.client.get(f'/api/cte-historicos-importados/{cte.pk}/fornecedor/status/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['fornecedor_id'], self.forn.id)
        cte.refresh_from_db()
        self.assertEqual(cte.fornecedor_remetente_id, self.forn.id)

    def test_cadastro_nao_gera_financeiro_automatico(self):
        cnpj_novo = _cnpj_valido()
        cnpj_digits = ''.join(c for c in cnpj_novo if c.isdigit())
        nf = _nf_sem_fornecedor(cnpj_xml=cnpj_digits)
        self.client.post(
            f'/api/nf-entradas-historicas-importadas/{nf.pk}/fornecedor/cadastrar-vincular/',
            {'razao_social': 'Novo Forn', 'cnpj': cnpj_novo, 'uf': 'SP'},
            format='json',
        )
        from apps.financeiro.models import TituloFinanceiro

        self.assertEqual(
            TituloFinanceiro.objects.filter(
                origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
                origem_id=nf.pk,
            ).count(),
            0,
        )
