# Generated manually for Fase 1 rastreabilidade CF ↔ conferência NF entrada

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal', '0010_nfe_entrada_conferencia'),
        ('qualidade', '0010_item_certificado_qualidade_rastreabilidade_saida'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='item_conferencia',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='itens_certificado_fornecedor',
                to='fiscal.itemnfeentradaconferencia',
            ),
        ),
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='origem_nfe_item_numero',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemcertificadofornecedorentrada',
            name='origem_vinculada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='itemcertificadofornecedorentrada',
            constraint=models.UniqueConstraint(
                condition=models.Q(('ativo', True), ('item_conferencia__isnull', False)),
                fields=('item_conferencia',),
                name='uniq_item_cf_item_conferencia_ativo',
            ),
        ),
    ]
