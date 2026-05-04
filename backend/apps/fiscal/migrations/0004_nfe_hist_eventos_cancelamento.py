import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('fiscal', '0003_nf_saida_historica_importada'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='cancelada',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='data_cancelamento',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='evento_cancelamento_id',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='evento_cancelamento_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='protocolo_evento',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='status_documento',
            field=models.CharField(default='autorizada', max_length=32),
        ),
        migrations.AddField(
            model_name='nfesaidahistoricaimportada',
            name='tipo_evento',
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.CreateModel(
            name='EventoNFeSaidaHistoricaImportada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chave_acesso', models.CharField(db_index=True, max_length=44)),
                ('tipo_evento', models.CharField(db_index=True, max_length=16)),
                ('protocolo_evento', models.CharField(blank=True, max_length=30)),
                ('id_evento', models.CharField(blank=True, max_length=80)),
                ('sequencial_evento', models.PositiveSmallIntegerField(default=0)),
                ('data_evento', models.DateTimeField(blank=True, null=True)),
                ('evento_json', models.JSONField(blank=True, default=dict)),
                ('nome_arquivo', models.CharField(blank=True, max_length=255)),
                ('importado_em', models.DateTimeField(auto_now_add=True)),
                (
                    'nf',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='eventos',
                        to='fiscal.nfesaidahistoricaimportada',
                    ),
                ),
            ],
            options={
                'ordering': ['-importado_em', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='eventonfesaidahistoricaimportada',
            constraint=models.UniqueConstraint(
                fields=('nf', 'tipo_evento', 'protocolo_evento', 'id_evento'),
                name='uniq_nf_hist_evento_dedup',
            ),
        ),
    ]
