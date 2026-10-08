from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Colaborador
from apps.comercial.models import Proposta, Vendedor
from apps.crm.models import Atividade, Lead
from apps.financeiro.models import TituloFinanceiro
from apps.produtos.models import Produto

from apps.fiscal.central_dfe.service import DocumentoCentralDfe

from apps.notificacoes.events import (
    gerar_notificacoes_pendentes,
    notificar_documento_central_dfe,
    notificar_atividade_vencida,
    notificar_estoque_minimo,
    notificar_proposta_aguardando_acao,
    notificar_titulo_vencido,
)
from apps.notificacoes.models import Notificacao
from apps.notificacoes.service import criar_notificacao, notificar_destinatarios, usuarios_destinatarios


class NotificacaoServiceTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='notif.user', password='senha-teste')
        self.outro = self.User.objects.create_user(username='notif.outro', password='senha-teste')

    def test_criacao_idempotente_por_usuario(self):
        primeira, criada = criar_notificacao(
            destinatario=self.user,
            modulo=Notificacao.Modulo.CRM,
            tipo=Notificacao.Tipo.NOVO_LEAD,
            titulo='Novo lead',
            mensagem='Lead recebido.',
            chave_idempotencia='lead:10',
        )
        segunda, criada_novamente = criar_notificacao(
            destinatario=self.user,
            modulo=Notificacao.Modulo.CRM,
            tipo=Notificacao.Tipo.NOVO_LEAD,
            titulo='Novo lead duplicado',
            mensagem='Não deve duplicar.',
            chave_idempotencia='lead:10',
        )

        self.assertTrue(criada)
        self.assertFalse(criada_novamente)
        self.assertEqual(primeira.pk, segunda.pk)
        self.assertEqual(Notificacao.objects.filter(destinatario=self.user).count(), 1)

    def test_mesmo_evento_pode_ser_enviado_a_usuarios_diferentes(self):
        criadas = notificar_destinatarios(
            modulo=Notificacao.Modulo.SISTEMA,
            tipo=Notificacao.Tipo.SISTEMA,
            titulo='Aviso geral',
            mensagem='Mensagem interna.',
            destinatarios=[self.user, self.outro],
            chave_idempotencia='aviso:1',
        )

        self.assertEqual(len(criadas), 2)
        self.assertEqual(Notificacao.objects.filter(chave_idempotencia__startswith='aviso:1').count(), 2)

    def test_destinatario_por_flag_de_area_e_staff(self):
        Colaborador.objects.create(
            nome='Responsável financeiro',
            usuario=self.user,
            ativo=True,
            eh_responsavel_financeiro=True,
        )
        self.outro.is_staff = True
        self.outro.save(update_fields=['is_staff'])

        usuarios = usuarios_destinatarios(modulo=Notificacao.Modulo.FINANCEIRO)

        self.assertEqual(set(usuarios.values_list('pk', flat=True)), {self.user.pk, self.outro.pk})

    def test_atividade_vencida_notifica_responsavel_sem_duplicar(self):
        colaborador = Colaborador.objects.create(
            nome='Vendedor CRM',
            usuario=self.user,
            ativo=True,
            eh_vendedor=True,
        )
        lead = Lead.objects.create(nome='Lead de teste de atividade')
        atividade = Atividade.objects.create(
            titulo='Retornar contato',
            lead=lead,
            responsavel=colaborador,
            agendada_para=timezone.now() - timedelta(hours=1),
        )

        primeira = notificar_atividade_vencida(atividade)
        segunda = notificar_atividade_vencida(atividade)

        self.assertEqual(len(primeira), 1)
        self.assertEqual(segunda, [])
        self.assertEqual(Notificacao.objects.filter(destinatario=self.user).count(), 1)
        self.assertEqual(Notificacao.objects.get(destinatario=self.user).tipo, Notificacao.Tipo.ATIVIDADE_VENCIDA)

    def test_proposta_aguardando_acao_notifica_vendedor_sem_duplicar(self):
        vendedor = Vendedor.objects.create(nome='Vendedor de proposta', usuario=self.user)
        proposta = Proposta.objects.create(
            numero='PROP-NOTIF-001',
            data=date.today(),
            validade=date.today() + timedelta(days=10),
            vendedor_ref=vendedor,
            status='EM_ANALISE',
        )

        primeira = notificar_proposta_aguardando_acao(proposta)
        segunda = notificar_proposta_aguardando_acao(proposta)

        self.assertEqual(len(primeira), 1)
        self.assertEqual(segunda, [])
        self.assertEqual(primeira[0].url_destino, '/propostas')
        self.assertEqual(primeira[0].destinatario_id, self.user.pk)

    def test_titulo_vencido_e_estoque_minimo_notificam_areas(self):
        Colaborador.objects.create(
            nome='Financeiro e estoque',
            usuario=self.user,
            ativo=True,
            eh_responsavel_financeiro=True,
            eh_responsavel_estoque=True,
        )
        titulo = TituloFinanceiro.objects.create(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            numero='TIT-NOTIF-001',
            data_emissao=date.today() - timedelta(days=10),
            data_vencimento=date.today() - timedelta(days=1),
            valor_original=Decimal('100.00'),
            valor_aberto=Decimal('100.00'),
            valor_baixado=Decimal('0.00'),
            criado_por=self.user,
        )
        produto = Produto.objects.create(
            descricao='Produto abaixo do mínimo',
            codigo_completo='PROD-NOTIF-001',
            estoque_minimo=Decimal('5.000'),
        )

        titulo_criado = notificar_titulo_vencido(titulo, hoje=date.today())
        estoque_criado = notificar_estoque_minimo(produto, saldo_disponivel=Decimal('1.000'))

        self.assertEqual(len(titulo_criado), 1)
        self.assertEqual(titulo_criado[0].prioridade, Notificacao.Prioridade.CRITICA)
        self.assertEqual(titulo_criado[0].url_destino, '/financeiro/contas-pagar')
        self.assertEqual(len(estoque_criado), 1)
        self.assertEqual(estoque_criado[0].modulo, Notificacao.Modulo.ESTOQUE)

    def test_documento_fiscal_central_dfe_notifica_area_e_idempotente(self):
        Colaborador.objects.create(
            nome='Responsável fiscal',
            usuario=self.user,
            ativo=True,
            eh_responsavel_fiscal=True,
        )
        documento = DocumentoCentralDfe(
            id=7,
            tipo_documento='NFE_ENTRADA',
            chave_resumida='3526...0007',
            chave_acesso='35260812345678000123550010000000071000000070',
            numero='7',
            serie='1',
            data_emissao=date.today(),
            data_importacao=timezone.now(),
            emitente_nome='Fornecedor de teste',
            emitente_cnpj='12345678000123',
            uf='SP',
            valor_total=Decimal('100.00'),
            status_entrada='PENDENTE_ENTRADA',
            status_entrada_label='Pendente de entrada',
            tipo_label='NF-e Fornecedor',
            detalhe_rota='/nfe-entrada-historica-importada',
            empresa_id=1,
        )

        primeira = notificar_documento_central_dfe(documento)
        segunda = notificar_documento_central_dfe(documento)

        self.assertEqual(len(primeira), 1)
        self.assertEqual(segunda, [])
        self.assertEqual(primeira[0].modulo, Notificacao.Modulo.FISCAL)
        self.assertEqual(primeira[0].tipo, Notificacao.Tipo.DOCUMENTO_FISCAL)
        self.assertEqual(primeira[0].url_destino, '/nfe-entrada-historica-importada')
        self.assertIn('Fornecedor de teste', primeira[0].mensagem)

    def test_lote_processa_atividade_vencida_com_idempotencia(self):
        colaborador = Colaborador.objects.create(
            nome='Vendedor CRM lote',
            usuario=self.user,
            ativo=True,
            eh_vendedor=True,
        )
        lead = Lead.objects.create(nome='Lead de teste de lote')
        Atividade.objects.create(
            titulo='Atividade vencida em lote',
            lead=lead,
            responsavel=colaborador,
            agendada_para=timezone.now() - timedelta(days=1),
        )

        primeira = gerar_notificacoes_pendentes()
        segunda = gerar_notificacoes_pendentes()

        self.assertEqual(primeira['atividades'], 1)
        self.assertEqual(segunda['atividades'], 0)
        self.assertEqual(Notificacao.objects.filter(destinatario=self.user).count(), 1)


class NotificacaoApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='notif.api', password='senha-teste')
        self.outro = User.objects.create_user(username='notif.api.outro', password='senha-teste')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.notificacao = Notificacao.objects.create(
            destinatario=self.user,
            modulo=Notificacao.Modulo.CRM,
            tipo=Notificacao.Tipo.NOVO_LEAD,
            prioridade=Notificacao.Prioridade.ALTA,
            titulo='Novo lead recebido',
            mensagem='Há um novo lead para atendimento.',
        )
        Notificacao.objects.create(
            destinatario=self.outro,
            modulo=Notificacao.Modulo.CRM,
            tipo=Notificacao.Tipo.NOVO_LEAD,
            titulo='Privada',
            mensagem='Não deve aparecer para o usuário atual.',
        )

    def test_listagem_e_contagem_isolam_por_usuario(self):
        response = self.client.get('/api/notificacoes/')
        count_response = self.client.get('/api/notificacoes/nao-lidas-count/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.notificacao.id)
        self.assertEqual(count_response.status_code, 200, count_response.data)
        self.assertEqual(count_response.data['count'], 1)

    def test_usuario_nao_pode_operar_notificacao_de_outro_usuario(self):
        response = self.client.post(f'/api/notificacoes/{Notificacao.objects.get(destinatario=self.outro).pk}/marcar-lida/')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Notificacao.objects.get(destinatario=self.outro).lida)

    def test_marcar_lida_arquivar_e_marcar_todas(self):
        response = self.client.post(f'/api/notificacoes/{self.notificacao.pk}/marcar-lida/')
        self.assertEqual(response.status_code, 200, response.data)
        self.notificacao.refresh_from_db()
        self.assertTrue(self.notificacao.lida)
        self.assertIsNotNone(self.notificacao.lida_em)

        segunda = Notificacao.objects.create(
            destinatario=self.user,
            modulo=Notificacao.Modulo.FINANCEIRO,
            tipo=Notificacao.Tipo.TITULO_VENCIDO,
            titulo='Título vencido',
            mensagem='Há um título vencido.',
        )
        todas = self.client.post('/api/notificacoes/marcar-todas-lidas/')
        self.assertEqual(todas.status_code, 200, todas.data)
        segunda.refresh_from_db()
        self.assertTrue(segunda.lida)

        arquivar_response = self.client.post(f'/api/notificacoes/{self.notificacao.pk}/arquivar/')
        self.assertEqual(arquivar_response.status_code, 200, arquivar_response.data)
        self.notificacao.refresh_from_db()
        self.assertTrue(self.notificacao.arquivada)
        self.assertIsNotNone(self.notificacao.arquivada_em)
        self.assertEqual(self.client.get('/api/notificacoes/').data['count'], 1)
