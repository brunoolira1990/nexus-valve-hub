from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.crm.models import Atividade, HistoricoLead, Lead, Oportunidade
from apps.crm.serializers import AtividadeSerializer


class Crm2ModelTests(TestCase):
    def test_serializer_atividade_exige_lead_ou_oportunidade(self):
        serializer = AtividadeSerializer(data={'titulo': 'Retorno comercial'})

        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_atividade_pode_ser_vinculada_a_lead(self):
        lead = Lead.objects.create(nome='Lead industrial')
        atividade = Atividade.objects.create(
            lead=lead,
            titulo='Ligar para o comprador',
            tipo=Atividade.Tipo.LIGACAO,
        )

        self.assertEqual(atividade.lead_id, lead.id)
        self.assertEqual(atividade.status, Atividade.Status.PENDENTE)

    def test_atividade_pode_ser_vinculada_a_oportunidade(self):
        lead = Lead.objects.create(nome='Lead de projeto')
        oportunidade = Oportunidade.objects.create(
            titulo='Projeto de válvulas',
            lead=lead,
            valor_estimado='12500.00',
            probabilidade=40,
        )
        atividade = Atividade.objects.create(
            oportunidade=oportunidade,
            titulo='Enviar proposta técnica',
            tipo=Atividade.Tipo.EMAIL,
        )

        self.assertEqual(atividade.oportunidade_id, oportunidade.id)
        self.assertEqual(atividade.oportunidade.lead_id, lead.id)

    def test_historico_preserva_evento_e_dados(self):
        lead = Lead.objects.create(nome='Lead com histórico')
        historico = HistoricoLead.objects.create(
            lead=lead,
            evento=HistoricoLead.Evento.STATUS_ALTERADO,
            titulo='Status alterado',
            descricao='Lead qualificado.',
            dados={'de': 'NOVO', 'para': 'QUALIFICANDO'},
        )

        self.assertEqual(historico.lead_id, lead.id)
        self.assertEqual(historico.dados['para'], 'QUALIFICANDO')


class Crm2ApiTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        self.user = get_user_model().objects.create_user(
            username='crm2.teste',
            password='senha-de-teste-nao-prod',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_api_atividade_cria_evento_no_historico(self):
        lead = Lead.objects.create(nome='Lead API CRM 2')
        response = self.client.post(
            '/api/crm/atividades/',
            {
                'titulo': 'Retorno de qualificação',
                'tipo': Atividade.Tipo.LIGACAO,
                'lead_id': lead.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        atividade = Atividade.objects.get(pk=response.data['id'])
        evento = HistoricoLead.objects.get(atividade=atividade)
        self.assertEqual(evento.lead_id, lead.id)
        self.assertEqual(evento.evento, HistoricoLead.Evento.ATIVIDADE_CRIADA)

        history_response = self.client.get(f'/api/crm/historico-leads/?lead_id={lead.id}')
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.data['count'], 1)
