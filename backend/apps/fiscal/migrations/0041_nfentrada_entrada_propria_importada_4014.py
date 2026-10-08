# ERP 4.0.14.x — NF-e Entrada operacional: entrada própria importada

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0001_initial'),
        ('fiscal', '0040_equivalencia_composicao_40137'),
    ]

    operations = [
        migrations.AddField(
            model_name='nfeentrada',
            name='chave_acesso',
            field=models.CharField(blank=True, db_index=True, max_length=44),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='serie',
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='empresa_emitente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_entradas_proprias_emitidas',
                to='cadastros.empresa',
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='cliente_destinatario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nf_entradas_proprias_destinatario',
                to='cadastros.cliente',
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='tipo_origem',
            field=models.CharField(
                choices=[
                    ('MANUAL', 'Manual'),
                    ('ENTRADA_PROPRIA_IMPORTADA', 'Entrada própria importada'),
                ],
                default='MANUAL',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='status_operacional',
            field=models.CharField(
                choices=[
                    ('RASCUNHO', 'Rascunho'),
                    ('IMPORTADA_PENDENTE_CONFERENCIA', 'Importada — pendente conferência'),
                ],
                default='RASCUNHO',
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='emit_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='dest_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='itens_json',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='xml_importado',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='nome_arquivo',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='nfeentrada',
            name='importado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='nfeentrada',
            name='fornecedor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='nf_entradas',
                to='cadastros.fornecedor',
            ),
        ),
        migrations.AddConstraint(
            model_name='nfeentrada',
            constraint=models.UniqueConstraint(
                condition=models.Q(('chave_acesso', ''), _negated=True),
                fields=('chave_acesso',),
                name='uniq_nf_entrada_chave_acesso_nao_vazia',
            ),
        ),
    ]
