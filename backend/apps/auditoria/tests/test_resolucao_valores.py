"""Resolução de FK, material legado e enums para exibição do histórico."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.serializers import EnriquecedorValores
from apps.produtos.material_models import Material
from apps.produtos.models import FamiliaProduto, Produto


def _familia(sufixo: str) -> FamiliaProduto:
    return FamiliaProduto.objects.create(
        codigo_figura=f'9{sufixo}',
        descricao_base='FLANGE CEGO INOX 304',
        tipo_regra_codigo=FamiliaProduto.TipoRegraCodigo.BASE_POLEGADA,
        tipo_dimensional=FamiliaProduto.TipoDimensional.NPS,
    )


class ResolucaoValoresApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('aud_val', 'aud_val@test.local', 'secret')
        ct = ContentType.objects.get_for_model(RegistroAuditoria)
        perm = Permission.objects.get(content_type=ct, codename='view_registroauditoria')
        self.user.user_permissions.add(perm)
        self.client.force_authenticate(user=self.user)

    def _registrar(self, alteracoes: dict) -> RegistroAuditoria:
        return RegistroAuditoria.objects.create(
            app_label='produtos',
            model_name='produto',
            object_id=777,
            operacao='UPDATE',
            alteracoes=alteracoes,
            ator=self.user,
        )

    def _historico(self) -> dict:
        r = self.client.get('/api/auditoria/objetos/produtos/produto/777/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return r.data['results'][0]['alteracoes']

    def test_fk_familia_vira_nome_da_familia(self):
        familia = _familia('001')
        self._registrar({'familia_id': {'antes': None, 'depois': familia.id}})
        depois = self._historico()['familia_id']['depois']
        self.assertEqual(depois['id'], familia.id)
        self.assertEqual(depois['nome'], '9001 — FLANGE CEGO INOX 304')
        # 'antes' segue nulo: sem FK antiga não há o que resolver.
        self.assertIsNone(self._historico()['familia_id']['antes'])

    def test_fk_familia_inexistente_fica_como_id(self):
        self._registrar({'familia_id': {'antes': 424242, 'depois': 424243}})
        alt = self._historico()['familia_id']
        self.assertEqual(alt['antes'], 424242)
        self.assertEqual(alt['depois'], 424243)

    def test_enum_de_controle_de_unidade_vira_rotulo(self):
        self._registrar({'tipo_controle_unidade': {'antes': 'PECA', 'depois': 'DIMENSIONAL'}})
        alt = self._historico()['tipo_controle_unidade']
        self.assertEqual(alt['antes']['nome'], 'Peça')
        self.assertEqual(alt['antes']['valor'], 'PECA')
        self.assertEqual(alt['depois']['nome'], 'Dimensional')

    def test_material_legado_aponta_para_catalogo(self):
        Material.objects.create(
            nome='Aço Carbono',
            nome_curto='AC',
            categoria=Material.Categoria.ACO_CARBONO,
            aliases=['ACO CARBONO'],
        )
        self._registrar({'material': {'antes': 'ACO CARBONO', 'depois': 'material maluco'}})
        alt = self._historico()['material']
        self.assertEqual(alt['antes']['nome'], 'Aço Carbono')
        self.assertEqual(alt['antes']['valor'], 'ACO CARBONO')
        self.assertEqual(alt['antes']['id'], Material.objects.get().pk)
        # Sem correspondência no catálogo, o texto cru permanece.
        self.assertEqual(alt['depois'], 'material maluco')

    def test_campo_sensivel_e_texto_livre_nao_mudam(self):
        self._registrar({
            'descricao': {'antes': 'VALVULA A', 'depois': 'VALVULA B'},
            'preco_venda': {'sensivel': True, 'alterado': True},
        })
        alt = self._historico()
        self.assertEqual(alt['descricao'], {'antes': 'VALVULA A', 'depois': 'VALVULA B'})
        self.assertEqual(alt['preco_venda'], {'sensivel': True, 'alterado': True})


class ResolucaoValoresEmLoteTests(APITestCase):
    def test_dois_registros_uma_consulta_de_familia(self):
        familia = _familia('002')
        for _ in range(2):
            RegistroAuditoria.objects.create(
                app_label='produtos',
                model_name='produto',
                object_id=1,
                operacao='UPDATE',
                alteracoes={'familia_id': {'antes': familia.id, 'depois': None}},
            )
        registros = list(RegistroAuditoria.objects.all())
        enriquecedor = EnriquecedorValores('produtos', 'produto')
        for registro in registros:
            enriquecedor.coletar(registro.alteracoes)
        with self.assertNumQueries(1):
            enriquecedor.carregar()
        with self.assertNumQueries(0):
            for registro in registros:
                alt = enriquecedor.enriquecer(registro.alteracoes)
                self.assertEqual(alt['familia_id']['antes']['nome'], '9002 — FLANGE CEGO INOX 304')

    def test_enriquecedor_usa_o_modelo_auditado_para_os_enums(self):
        enriquecedor = EnriquecedorValores('produtos', 'produto')
        enriquecedor.coletar({'modo_codigo': {'antes': 'LEGADO', 'depois': 'INTERNO'}})
        enriquecedor.carregar()
        alt = enriquecedor.enriquecer({'modo_codigo': {'antes': 'LEGADO', 'depois': 'INTERNO'}})
        self.assertEqual(alt['modo_codigo']['antes']['nome'], Produto.ModoCodigo.LEGADO.label)
        self.assertEqual(alt['modo_codigo']['depois']['nome'], Produto.ModoCodigo.INTERNO.label)
