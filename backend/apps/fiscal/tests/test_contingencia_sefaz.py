"""Testes do módulo de contingência SEFAZ (NF-e).

Cobertura:
- Bloqueio de tpEmis inválido/descontinuado (DPEC, FSDA, off-line DFe).
- Registro e encerramento de contingência (uma ativa por vez).
- Emissão em contingência (EPEC): chave recomputada com tpEmis=2, XML assinado,
  status XML_ASSINADO, evento registrado.
- Transmissão de pendentes (mock da transmissão normal).
"""

from datetime import datetime, timedelta, timezone as dt_tz

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from apps.fiscal.contingencia_sefaz import (
    PRAZO_CONTINGENCIA_HORAS,
    ContingenciaSefazError,
    encerrar_contingencia,
    emitir_em_contingencia,
    registrar_contingencia,
    transmitir_pendentes_contingencia,
)
from apps.fiscal.models import ContingenciaSefaz, NFeSaida


class _FixtureMixin:
    """Helpers mínimos para fixtures compartilhados entre os testes."""

    def _empresa(self):
        from apps.cadastros.models import Empresa

        # Padrão dos testes de emissão existentes: campos mínimos e CNPJ
        # determinístico válido. A IE é complementada pela camada de preview
        # quando a empresa possui insenção configurada em homologação.
        empresa, _ = Empresa.objects.update_or_create(
            cnpj='12345678000195',
            defaults={
                'razao_social': 'Empresa Contingência Validação',
                'uf': 'SP',
                'ie': '110042490114',
                'regime_tributario': 'Lucro Presumido',
                'senha_certificado': 'test123',
            },
        )
        if not empresa.certificado_arquivo:
            pfx_bytes = _gerar_pfx_teste()
            empresa.certificado_arquivo.save('t.pfx', ContentFile(pfx_bytes), save=True)
        _garantir_numeracao(empresa)
        return empresa

    def _pedido_e_nf(self, empresa, status=NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO):
        from apps.comercial.models import PedidoVenda
        from apps.fiscal.models import ItemNFeSaida
        from apps.produtos.models import Produto

        pedido, _ = PedidoVenda.objects.get_or_create(
            numero='PV-CONTING',
            defaults={
                'cliente': self._cliente(),
                'empresa_emitente': empresa,
                'data': timezone.now().date(),
                'valor_total': '100.00',
                'status': 'CONCLUIDO',
            },
        )
        produto, _ = Produto.objects.get_or_create(
            codigo_completo='SKU-CONTING',
            defaults={
                'descricao': 'Produto Contingência',
                'ncm': '84818200',
                'preco_venda': '100.00',
                'tipo_fisico': 'valvula',
                'unidade_venda_padrao': 'UN',
            },
        )
        nf, _ = NFeSaida.objects.get_or_create(
            numero='RASCUNHO-CONTING',
            defaults={
                'pedido_venda': pedido,
                'cliente': pedido.cliente,
                'data': timezone.now(),
                'status_emissao_sefaz': status,
                'ambiente_emissao': NFeSaida.AmbienteEmissao.HOMOLOGACAO,
                'indicadores_fiscais_confirmados': True,
                'tipo_emissao': '1',
                'empresa_emitente': empresa,
            },
        )
        ItemNFeSaida.objects.get_or_create(
            nf=nf,
            produto=produto,
            defaults={
                'quantidade': '1.000',
                'valor': '100.00',
                'snapshot_fiscal': {'cfop': '5102', 'cst_icms': '00', 'ncm': '84818200'},
            },
        )
        return nf

    def _cliente(self):
        from apps.cadastros.models import Cliente

        cliente, _ = Cliente.objects.get_or_create(
            cnpj='51021317000199',
            defaults={
                'razao_social': 'Cliente Contingência',
                'uf': 'RJ',
                'cidade': 'Rio de Janeiro',
                'ie_isento': True,
            },
        )
        return cliente


def _gerar_pfx_teste(senha: str = 'test123') -> bytes:
    """Gera um PFX autoassinado de teste (equivalente ao helper do teste 402)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Empresa Teste')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(dt_tz.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(dt_tz.utc) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return serialization.pkcs12.serialize_key_and_certificates(
        b'cert', key, cert, None, serialization.BestAvailableEncryption(senha.encode()),
    )


def _garantir_numeracao(empresa):
    from apps.fiscal.nfe_emissao.numeracao_defaults import ensure_numeracao_padrao_nfe

    ensure_numeracao_padrao_nfe(empresa)


class ContingenciaRegistroTest(TestCase):
    def test_tp_emis_normal_rejeitado(self):
        empresa = _FixtureMixin()._empresa()
        with self.assertRaises(ContingenciaSefazError) as ctx:
            registrar_contingencia(empresa, motivo='teste', tp_emis='1')
        self.assertIn('não é um modo de contingência', str(ctx.exception))

    def test_tp_emis_descontinuados_bloqueados(self):
        empresa = _FixtureMixin()._empresa()
        for tp in ('4', '5', '9'):
            with self.subTest(tp=tp), self.assertRaises(ContingenciaSefazError):
                registrar_contingencia(empresa, motivo='teste', tp_emis=tp)

    def test_registrar_e_encerrar(self):
        empresa = _FixtureMixin()._empresa()
        reg = registrar_contingencia(empresa, motivo='SEFAZ fora do ar', tp_emis='2')
        self.assertEqual(reg.tp_emis, '2')
        self.assertTrue(reg.ativa)
        with self.assertRaises(ContingenciaSefazError):
            registrar_contingencia(empresa, motivo='segunda', tp_emis='2')
        enc = encerrar_contingencia(empresa)
        self.assertFalse(enc.ativa)
        self.assertIsNotNone(enc.encerrada_em)
        # Nova contingência pode ser ativada após encerrar.
        reg2 = registrar_contingencia(empresa, motivo='nova', tp_emis='7')
        self.assertEqual(reg2.tp_emis, '7')


class ContingenciaEmissaoTest(_FixtureMixin, TestCase):
    def test_emitir_epec_recomputa_chave(self):
        mixin = _FixtureMixin()
        empresa = mixin._empresa()
        nf = mixin._pedido_e_nf(empresa)
        _garantir_numeracao(empresa)
        # Reservar numeração (chave real com tpEmis=1).
        from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe

        reservar_numeracao_nfe(nf, usuario=None)
        nf.refresh_from_db()
        chave_original = nf.chave_acesso
        self.assertEqual(chave_original[34:35], '1')

        registrar_contingencia(empresa, motivo='teste epec', tp_emis='2')
        resultado = emitir_em_contingencia(nf, usuario=None)

        nf.refresh_from_db()
        self.assertEqual(nf.tipo_emissao, '2')
        self.assertEqual(nf.chave_acesso[34:35], '2')
        self.assertNotEqual(nf.chave_acesso, chave_original)
        self.assertEqual(nf.status_emissao_sefaz, NFeSaida.StatusEmissaoSefaz.XML_ASSINADO)
        self.assertIn('<tpEmis>2</tpEmis>', nf.xml_assinado)
        self.assertEqual(resultado['tp_emis'], '2')
        self.assertEqual(resultado['prazo_horas'], PRAZO_CONTINGENCIA_HORAS)
        self.assertTrue(nf.eventos.filter(tipo_evento='CONTINGENCIA_EPEC_ATIVADA').exists())

    def test_emitir_sem_contingencia_ativa_rejeita(self):
        mixin = _FixtureMixin()
        empresa = mixin._empresa()
        nf = mixin._pedido_e_nf(empresa)
        with self.assertRaises(ContingenciaSefazError) as ctx:
            emitir_em_contingencia(nf, usuario=None)
        self.assertIn('Nenhuma contingência', str(ctx.exception))

    def test_dupla_emissao_contingencia_rejeitada(self):
        mixin = _FixtureMixin()
        empresa = mixin._empresa()
        nf = mixin._pedido_e_nf(empresa)
        _garantir_numeracao(empresa)
        from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe

        reservar_numeracao_nfe(nf, usuario=None)
        registrar_contingencia(empresa, motivo='teste', tp_emis='2')
        emitir_em_contingencia(nf, usuario=None)
        with self.assertRaises(ContingenciaSefazError) as ctx:
            emitir_em_contingencia(nf, usuario=None)
        self.assertIn('já emitida em modo de contingência', str(ctx.exception))

    def test_transmitir_pendentes(self):
        mixin = _FixtureMixin()
        empresa = mixin._empresa()
        nf = mixin._pedido_e_nf(empresa)
        _garantir_numeracao(empresa)
        from apps.fiscal.nfe_emissao.numeracao import reservar_numeracao_nfe

        reservar_numeracao_nfe(nf, usuario=None)
        registrar_contingencia(empresa, motivo='teste', tp_emis='2')
        emitir_em_contingencia(nf, usuario=None)

        # Mock: a transmissão normal é chamada com a NF de contingência.
        import unittest.mock as mock

        with mock.patch('apps.fiscal.contingencia_sefaz._transmitir_nf_contingencia') as tx:
            tx.return_value = {'autorizada': True}
            resumo = transmitir_pendentes_contingencia(empresa, usuario=None)

        self.assertEqual(resumo['total'], 1)
        self.assertEqual(len(resumo['sucesso']), 1)
        self.assertEqual(len(resumo['falhas']), 0)
        tx.assert_called_once()
        nf.refresh_from_db()
        self.assertEqual(nf.tipo_emissao, '2')
