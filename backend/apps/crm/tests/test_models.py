from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.crm.models import Lead, Oportunidade


class CrmModelTests(TestCase):
    def test_lead_preserva_cnpj_alfanumerico_normalizado(self):
        lead = Lead.objects.create(
            nome='Cliente de homologação CRM',
            cnpj='00.000.000/E08G-12',
            uf='sp',
        )

        self.assertEqual(lead.cnpj, '00000000E08G12')
        self.assertEqual(lead.uf, 'SP')

    def test_lead_nao_permite_cnpj_alfanumerico_duplicado(self):
        Lead.objects.create(nome='Primeiro lead', cnpj='00000000E08G12')

        with self.assertRaises(Exception):
            Lead.objects.create(nome='Segundo lead', cnpj='00.000.000/E08G-12')

    def test_oportunidade_exige_lead_ou_cliente(self):
        with self.assertRaises(ValidationError):
            from apps.crm.serializers import OportunidadeSerializer

            serializer = OportunidadeSerializer(data={
                'titulo': 'Oportunidade sem origem',
                'valor_estimado': '1000.00',
            })
            serializer.is_valid(raise_exception=True)

    def test_oportunidade_pode_ser_criada_a_partir_de_lead(self):
        lead = Lead.objects.create(nome='Lead industrial')
        oportunidade = Oportunidade.objects.create(
            titulo='Projeto válvulas especiais',
            lead=lead,
            valor_estimado='12500.00',
            probabilidade=40,
        )

        self.assertEqual(oportunidade.lead_id, lead.id)
        self.assertEqual(oportunidade.status, Oportunidade.Status.ABERTA)
