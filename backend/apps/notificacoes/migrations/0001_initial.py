from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notificacao',
            fields=[
                (
                    'id',
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
                ),
                (
                    'modulo',
                    models.CharField(
                        choices=[
                            ('COMERCIAL', 'Comercial'),
                            ('FISCAL', 'Fiscal'),
                            ('FINANCEIRO', 'Financeiro'),
                            ('ESTOQUE', 'Estoque'),
                            ('QUALIDADE', 'Qualidade'),
                            ('COMPRAS', 'Compras'),
                            ('CADASTROS', 'Cadastros'),
                            ('ATENDIMENTOS', 'Atendimentos'),
                            ('CRM', 'CRM'),
                            ('SISTEMA', 'Sistema'),
                        ],
                        db_index=True,
                        default='SISTEMA',
                        max_length=20,
                    ),
                ),
                (
                    'tipo',
                    models.CharField(
                        choices=[
                            ('NOVO_LEAD', 'Novo lead'),
                            ('ATIVIDADE_VENCIDA', 'Atividade vencida'),
                            ('TITULO_VENCIDO', 'Título financeiro vencido'),
                            ('ESTOQUE_MINIMO', 'Estoque abaixo do mínimo'),
                            ('PROPOSTA_ACAO', 'Proposta aguardando ação'),
                            ('PENDENCIA_OPERACIONAL', 'Pendência operacional'),
                            ('DOCUMENTO_FISCAL', 'Documento fiscal'),
                            ('SISTEMA', 'Aviso do sistema'),
                        ],
                        db_index=True,
                        default='SISTEMA',
                        max_length=32,
                    ),
                ),
                (
                    'prioridade',
                    models.CharField(
                        choices=[
                            ('BAIXA', 'Baixa'),
                            ('NORMAL', 'Normal'),
                            ('ALTA', 'Alta'),
                            ('CRITICA', 'Crítica'),
                        ],
                        db_index=True,
                        default='NORMAL',
                        max_length=10,
                    ),
                ),
                ('titulo', models.CharField(max_length=180)),
                ('mensagem', models.TextField()),
                ('url_destino', models.CharField(blank=True, max_length=500)),
                ('objeto_tipo', models.CharField(blank=True, max_length=80)),
                ('objeto_id', models.CharField(blank=True, max_length=80)),
                ('chave_idempotencia', models.CharField(blank=True, max_length=180)),
                ('lida', models.BooleanField(db_index=True, default=False)),
                ('arquivada', models.BooleanField(db_index=True, default=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('lida_em', models.DateTimeField(blank=True, null=True)),
                ('arquivada_em', models.DateTimeField(blank=True, null=True)),
                (
                    'destinatario',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='notificacoes',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Notificação',
                'verbose_name_plural': 'Notificações',
                'ordering': ['-criado_em', '-id'],
                'indexes': [
                    models.Index(
                        fields=['destinatario', 'arquivada', '-criado_em'],
                        name='notif_recipient_archive_idx',
                    ),
                    models.Index(
                        fields=['destinatario', 'lida', 'arquivada'],
                        name='notif_recipient_read_idx',
                    ),
                    models.Index(
                        fields=['tipo', 'objeto_tipo', 'objeto_id'],
                        name='notif_type_object_idx',
                    ),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        condition=models.Q(chave_idempotencia__gt=''),
                        fields=('destinatario', 'chave_idempotencia'),
                        name='notif_recipient_idempotency_uniq',
                    ),
                ],
            },
        ),
    ]
