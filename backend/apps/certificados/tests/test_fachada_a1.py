"""C0 — Fachada neutra A1: segurança, isolamento e ausência de efeitos fiscais."""

from __future__ import annotations

import ast
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.cadastros.models import Empresa
from apps.certificados.contratos import FinalidadeCertificado, MaterialCriptograficoA1
from apps.certificados.exceptions import (
    CODE_FINALIDADE_NAO_SUPORTADA,
    CODE_NAO_CONFIGURADO,
    CODE_SENHA_INVALIDA,
    CertificadoDigitalError,
)
from apps.certificados.servico_a1 import CertificadoDigitalA1Facade
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error


def _pfx_bytes(*, senha: str = 'segredo-teste', dias_validos: int = 365) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, 'Fixture Neutra A1 12345678000199')]
    )
    agora = datetime.now(timezone.utc)
    if dias_validos >= 0:
        not_before = agora - timedelta(days=1)
        not_after = agora + timedelta(days=dias_validos)
    else:
        # Expirado: validade no passado, com intervalo válido.
        not_after = agora + timedelta(days=dias_validos)  # negativo
        not_before = not_after - timedelta(days=30)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b'nexus-c0',
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(senha.encode()),
    )


def _empresa_com_pfx(
    *,
    senha: str = 'segredo-teste',
    dias_validos: int = 365,
    cnpj: str = '12345678000199',
) -> Empresa:
    emp = Empresa.objects.create(
        razao_social=f'Empresa C0 {cnpj[-4:]}',
        cnpj=cnpj,
        uf='SP',
        senha_certificado=senha,
    )
    emp.certificado_arquivo.save(
        f'fixture_c0_{cnpj[-4:]}.pfx',
        SimpleUploadedFile('fixture_c0.pfx', _pfx_bytes(senha=senha, dias_validos=dias_validos)),
        save=True,
    )
    return emp


class ArquiteturaPacoteCertificadosTests(TestCase):
    """Garante que o pacote neutro não importa emissão/SEFAZ/XML/DANFE/BFR."""

    PROIBIDOS = (
        'apps.fiscal.nfe_emissao',
        'ComunicacaoSefaz',
        'AssinaturaA1',
        'danfe',
        'bfr',
        'nfe_emissao',
    )

    def test_imports_do_pacote_nao_puxam_emissao(self):
        root = Path(__file__).resolve().parents[1]
        ofensores: list[str] = []
        for path in root.rglob('*.py'):
            if 'tests' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ''
                    mods = [base] + [f'{base}.{a.name}' if base else a.name for a in node.names]
                texto = ' '.join(mods).lower()
                for proibido in self.PROIBIDOS:
                    if proibido.lower() in texto:
                        ofensores.append(f'{path.name}:{proibido}')
        self.assertEqual(ofensores, [], msg=f'Imports proibidos: {ofensores}')


class FachadaCertificadoA1Tests(TestCase):
    def setUp(self):
        self.facade = CertificadoDigitalA1Facade()

    def test_valida_certificado_disponivel(self):
        emp = _empresa_com_pfx()
        meta = self.facade.validar_disponibilidade(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        self.assertTrue(meta.disponivel)
        self.assertTrue(meta.valido)
        self.assertEqual(meta.tipo, 'A1')
        self.assertEqual(meta.finalidade, 'CONSULTA_CENPROT')
        self.assertIsNotNone(meta.vence_em)

    def test_ausente_erro_sanitizado(self):
        emp = Empresa.objects.create(razao_social='Sem Cert', cnpj='11111111000191', uf='SP')
        with self.assertRaises(CertificadoDigitalError) as ctx:
            self.facade.validar_disponibilidade(emp, FinalidadeCertificado.FISCAL_SEFAZ)
        self.assertEqual(ctx.exception.code, CODE_NAO_CONFIGURADO)
        self.assertNotIn('/', ctx.exception.detail)
        self.assertNotIn('.pfx', ctx.exception.detail.lower())

    def test_senha_invalida_nao_aparece_na_mensagem(self):
        emp = _empresa_com_pfx(senha='correta', cnpj='11222333000181')
        Empresa.objects.filter(pk=emp.pk).update(senha_certificado='errada')
        emp.refresh_from_db()
        with self.assertRaises(CertificadoDigitalError) as ctx:
            self.facade.validar_disponibilidade(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        self.assertEqual(ctx.exception.code, CODE_SENHA_INVALIDA)
        self.assertNotIn('errada', ctx.exception.detail)
        self.assertNotIn('segredo', ctx.exception.detail.lower())
        self.assertNotIn('.pfx', ctx.exception.detail.lower())
        self.assertNotIn('/', ctx.exception.detail)

    def test_caminho_nao_aparece_em_erro_de_arquivo(self):
        emp = _empresa_com_pfx()
        with patch(
            'apps.certificados.servico_a1.carregar_certificado_empresa',
            side_effect=CertificadoA1Error(
                'Arquivo não encontrado: /segredo/media/certificados/x.pfx'
            ),
        ):
            with self.assertRaises(CertificadoDigitalError) as ctx:
                self.facade.validar_disponibilidade(emp, FinalidadeCertificado.FISCAL_SEFAZ)
        self.assertNotIn('/segredo', ctx.exception.detail)
        self.assertNotIn('x.pfx', ctx.exception.detail)

    def test_expirado_identificado(self):
        emp = _empresa_com_pfx(dias_validos=-5, cnpj='99888777000166')
        meta = self.facade.obter_metadados_seguros(emp, FinalidadeCertificado.FISCAL_SEFAZ)
        self.assertFalse(meta.valido)
        self.assertIn('expir', (meta.motivo_indisponibilidade or '').lower())
        with self.assertRaises(CertificadoDigitalError) as ctx:
            self.facade.validar_disponibilidade(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        self.assertEqual(ctx.exception.code, 'CERTIFICADO_EXPIRADO')

    def test_falha_cenprot_nao_afeta_chamada_fiscal_posterior(self):
        emp_sem = Empresa.objects.create(
            razao_social='Sem Cert 2', cnpj='03999102000150', uf='SP'
        )
        with self.assertRaises(CertificadoDigitalError):
            self.facade.validar_disponibilidade(emp_sem, FinalidadeCertificado.CONSULTA_CENPROT)
        emp2 = _empresa_com_pfx(cnpj='32241095000121')
        info = carregar_certificado_empresa(emp2)
        self.assertTrue(info.valido)
        meta = self.facade.validar_disponibilidade(emp2, FinalidadeCertificado.FISCAL_SEFAZ)
        self.assertTrue(meta.valido)

    def test_metadados_nao_expoe_subject_serial_fingerprint(self):
        emp = _empresa_com_pfx()
        meta = self.facade.obter_metadados_seguros(emp, FinalidadeCertificado.FISCAL_SEFAZ)
        blob = str(meta.__dict__)
        self.assertNotIn('Fixture Neutra', blob)
        self.assertNotIn('12345678000199', blob)
        self.assertNotIn('subject', blob.lower())
        self.assertNotIn('serial', blob.lower())
        self.assertNotIn('fingerprint', blob.lower())
        self.assertNotIn('thumbprint', blob.lower())
        self.assertNotIn('issuer', blob.lower())
        self.assertNotIn('caminho', blob.lower())
        self.assertNotIn('.pfx', blob.lower())

    def test_material_em_memoria_e_liberacao(self):
        emp = _empresa_com_pfx()
        mat = self.facade.carregar_material_criptografico(
            emp, FinalidadeCertificado.CONSULTA_CENPROT
        )
        self.assertIsInstance(mat, MaterialCriptograficoA1)
        self.assertIsNotNone(mat.chave_privada)
        self.assertIsNotNone(mat.certificado)
        self.facade.liberar_material(mat)
        self.assertTrue(mat._liberado)
        self.assertIsNone(mat.chave_privada)
        self.assertIsNone(mat.certificado)

    def test_material_nao_e_json_serializavel(self):
        import json

        emp = _empresa_com_pfx()
        mat = self.facade.carregar_material_criptografico(emp, FinalidadeCertificado.FISCAL_SEFAZ)
        with self.assertRaises((TypeError, ValueError)):
            json.dumps(mat)
        self.facade.liberar_material(mat)

    @patch('urllib.request.urlopen')
    @patch('socket.create_connection')
    def test_zero_http_e_socket(self, mock_sock, mock_url):
        emp = _empresa_com_pfx()
        self.facade.validar_disponibilidade(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        self.facade.obter_metadados_seguros(emp, FinalidadeCertificado.FISCAL_SEFAZ)
        mat = self.facade.carregar_material_criptografico(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        self.facade.liberar_material(mat)
        mock_url.assert_not_called()
        mock_sock.assert_not_called()

    def test_nenhum_pem_nem_tmp_criado_pela_fachada(self):
        emp = _empresa_com_pfx()
        before = set(Path(tempfile.gettempdir()).glob('*'))
        mat = self.facade.carregar_material_criptografico(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        after = set(Path(tempfile.gettempdir()).glob('*'))
        novos = after - before
        for p in novos:
            self.assertFalse(str(p).lower().endswith(('.pem', '.key', '.crt')))
        self.facade.liberar_material(mat)

    def test_finalidade_desconhecida(self):
        emp = _empresa_com_pfx()
        with self.assertRaises(CertificadoDigitalError) as ctx:
            self.facade.validar_disponibilidade(emp, 'ASSINATURA_PDF')
        self.assertEqual(ctx.exception.code, CODE_FINALIDADE_NAO_SUPORTADA)

    def test_nenhum_model_alterado_pela_fachada(self):
        emp = _empresa_com_pfx()
        senha = emp.senha_certificado
        nome_arquivo = emp.certificado_arquivo.name
        self.facade.obter_metadados_seguros(emp, FinalidadeCertificado.CONSULTA_CENPROT)
        emp.refresh_from_db()
        self.assertEqual(emp.senha_certificado, senha)
        self.assertEqual(emp.certificado_arquivo.name, nome_arquivo)

    def test_imports_fiscais_atuais_permanecem(self):
        from apps.fiscal.nfe_integracao.adapters.certificado_a1 import (
            carregar_certificado_empresa as c1,
            validar_certificado_pfx as v1,
        )

        self.assertTrue(callable(c1) and callable(v1))
