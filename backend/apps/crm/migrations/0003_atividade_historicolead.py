# Generated manually for CRM 2 activities and lead history.
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('crm', '0002_lead_site_attribution'),
    ]

    operations = [
        migrations.CreateModel(
            name='Atividade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=255)),
                ('tipo', models.CharField(choices=[('LIGACAO', 'Ligação'), ('EMAIL', 'E-mail'), ('WHATSAPP', 'WhatsApp'), ('REUNIAO', 'Reunião'), ('VISITA', 'Visita'), ('TAREFA', 'Tarefa'), ('NOTA', 'Nota'), ('OUTRA', 'Outra')], default='TAREFA', max_length=20)),
                ('status', models.CharField(choices=[('PENDENTE', 'Pendente'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], default='PENDENTE', max_length=12)),
                ('descricao', models.TextField(blank=True)),
                ('agendada_para', models.DateTimeField(blank=True, null=True)),
                ('concluida_em', models.DateTimeField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='atividades', to='crm.lead')),
                ('oportunidade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='atividades', to='crm.oportunidade')),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='atividades_crm', to='cadastros.colaborador')),
            ],
            options={
                'verbose_name': 'Atividade CRM',
                'verbose_name_plural': 'Atividades CRM',
                'ordering': ['agendada_para', '-criado_em', '-id'],
                'indexes': [
                    models.Index(fields=['lead', 'status', 'agendada_para'], name='crm_activity_lead_due_idx'),
                    models.Index(fields=['oportunidade', 'status', 'agendada_para'], name='crm_activity_opp_due_idx'),
                    models.Index(fields=['responsavel', 'status', 'agendada_para'], name='crm_activity_resp_due_idx'),
                ],
                'constraints': [
                    models.CheckConstraint(condition=Q(('lead__isnull', False)) | Q(('oportunidade__isnull', False)), name='crm_activity_lead_or_opp_required'),
                ],
            },
        ),
        migrations.CreateModel(
            name='HistoricoLead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evento', models.CharField(choices=[('CRIADO', 'Lead criado'), ('STATUS_ALTERADO', 'Status alterado'), ('RESPONSAVEL_ALTERADO', 'Responsável alterado'), ('ATIVIDADE_CRIADA', 'Atividade criada'), ('ATIVIDADE_ATUALIZADA', 'Atividade atualizada'), ('NOTA', 'Nota adicionada'), ('CONVERSAO', 'Lead convertido'), ('OUTRO', 'Outro evento')], default='OUTRO', max_length=24)),
                ('titulo', models.CharField(max_length=255)),
                ('descricao', models.TextField(blank=True)),
                ('dados', models.JSONField(blank=True, default=dict)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atividade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos_historico', to='crm.atividade')),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico', to='crm.lead')),
                ('realizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='historicos_crm', to='cadastros.colaborador')),
            ],
            options={
                'verbose_name': 'Histórico de Lead',
                'verbose_name_plural': 'Históricos de Leads',
                'ordering': ['-criado_em', '-id'],
                'indexes': [
                    models.Index(fields=['lead', '-criado_em'], name='crm_lead_history_created_idx'),
                    models.Index(fields=['evento', '-criado_em'], name='crm_history_event_created_idx'),
                ],
            },
        ),
    ]
