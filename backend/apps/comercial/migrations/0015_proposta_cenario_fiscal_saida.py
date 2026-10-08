from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            'regras_fiscais',
            '0010_rename_regras_fisc_ativo_p_saida_idx_regras_fisc_ativo_e9258d_idx_and_more',
        ),
        ('comercial', '0014_pedidocompra_observacoes'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='usar_cenario_fiscal_saida',
            field=models.BooleanField(
                default=False,
                help_text='Quando ativo, tributos de saída usam o cenário fiscal novo (com fallback legado).',
            ),
        ),
        migrations.AddField(
            model_name='proposta',
            name='cenario_fiscal_saida',
            field=models.ForeignKey(
                blank=True,
                help_text='Cenário de saída desta proposta; vazio usa o cenário padrão ativo.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='propostas',
                to='regras_fiscais.cenariofiscalsaida',
            ),
        ),
    ]
