from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('cadastros', '0017_alter_transportadora_cnpj'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('cnpj', models.CharField(blank=True, max_length=20)),
                ('nome_contato', models.CharField(blank=True, max_length=160)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('telefone', models.CharField(blank=True, max_length=64)),
                ('cidade', models.CharField(blank=True, max_length=128)),
                ('uf', models.CharField(blank=True, max_length=2)),
                ('origem', models.CharField(choices=[('INDICACAO', 'Indicação'), ('SITE', 'Site'), ('WHATSAPP', 'WhatsApp'), ('TELEFONE', 'Telefone'), ('EVENTO', 'Evento'), ('OUTRA', 'Outra')], default='OUTRA', max_length=20)),
                ('status', models.CharField(choices=[('NOVO', 'Novo'), ('QUALIFICANDO', 'Em qualificação'), ('CONVERTIDO', 'Convertido'), ('DESCARTADO', 'Descartado')], default='NOVO', max_length=20)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads_crm', to='cadastros.cliente')),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads_crm', to='cadastros.colaborador')),
            ],
            options={
                'verbose_name': 'Lead CRM',
                'verbose_name_plural': 'Leads CRM',
                'ordering': ['-atualizado_em', '-id'],
            },
        ),
        migrations.CreateModel(
            name='Oportunidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('ABERTA', 'Aberta'), ('GANHA', 'Ganha'), ('PERDIDA', 'Perdida')], default='ABERTA', max_length=12)),
                ('etapa', models.CharField(choices=[('QUALIFICACAO', 'Qualificação'), ('ESPECIFICACAO', 'Especificação técnica'), ('PROPOSTA', 'Proposta'), ('NEGOCIACAO', 'Negociação'), ('FECHAMENTO', 'Fechamento')], default='QUALIFICACAO', max_length=20)),
                ('valor_estimado', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('probabilidade', models.PositiveSmallIntegerField(default=0)),
                ('previsao_fechamento', models.DateField(blank=True, null=True)),
                ('proxima_acao', models.DateField(blank=True, null=True)),
                ('motivo_perda', models.CharField(blank=True, max_length=255)),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='oportunidades_crm', to='cadastros.cliente')),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='oportunidades', to='crm.lead')),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='oportunidades_crm', to='cadastros.colaborador')),
            ],
            options={
                'verbose_name': 'Oportunidade CRM',
                'verbose_name_plural': 'Oportunidades CRM',
                'ordering': ['-atualizado_em', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['status', '-atualizado_em'], name='crm_lead_status_upd_idx'),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['responsavel', 'status'], name='crm_lead_resp_status_idx'),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['-atualizado_em', '-id'], name='crm_lead_updated_id_idx'),
        ),
        migrations.AddConstraint(
            model_name='lead',
            constraint=models.UniqueConstraint(condition=Q(('cnpj__gt', '')), fields=('cnpj',), name='crm_lead_cnpj_unique_nonblank'),
        ),
        migrations.AddIndex(
            model_name='oportunidade',
            index=models.Index(fields=['status', 'etapa', '-atualizado_em'], name='crm_opp_status_stage_idx'),
        ),
        migrations.AddIndex(
            model_name='oportunidade',
            index=models.Index(fields=['responsavel', 'status', 'proxima_acao'], name='crm_opp_resp_action_idx'),
        ),
        migrations.AddIndex(
            model_name='oportunidade',
            index=models.Index(fields=['previsao_fechamento', 'status'], name='crm_opp_forecast_status_idx'),
        ),
        migrations.AddIndex(
            model_name='oportunidade',
            index=models.Index(fields=['-atualizado_em', '-id'], name='crm_opp_updated_id_idx'),
        ),
        migrations.AddConstraint(
            model_name='oportunidade',
            constraint=models.CheckConstraint(condition=Q(('probabilidade__gte', 0)) & Q(('probabilidade__lte', 100)), name='crm_opp_probability_0_100'),
        ),
    ]
