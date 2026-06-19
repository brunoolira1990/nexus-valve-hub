from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

STATUS_ITEM_CONVERTIDO = 'CONVERTIDO_EM_PEDIDO'
STATUS_ITEM_PENDENTE = 'PENDENTE'
STATUS_ITEM_CANCELADO = 'CANCELADO'
STATUS_ITEM_PERDIDO = 'PERDIDO'
STATUS_ITEM_MANTIDO = 'MANTIDO_PARA_DEPOIS'

SNAPSHOT_STATUSES = frozenset(
    {
        STATUS_ITEM_PENDENTE,
        STATUS_ITEM_CANCELADO,
        STATUS_ITEM_PERDIDO,
        STATUS_ITEM_MANTIDO,
    }
)


def _parse_iso_datetime(value):
    if not value:
        return None
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    parsed = parse_datetime(str(value))
    if parsed is not None and timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def preencher_status_comercial_itens(apps, schema_editor):
    from django.utils import timezone

    ItemProposta = apps.get_model('comercial', 'ItemProposta')
    ItemPedidoVenda = apps.get_model('comercial', 'ItemPedidoVenda')

    links = {}
    for ipv in (
        ItemPedidoVenda.objects.filter(item_proposta_id__isnull=False)
        .order_by('item_proposta_id', 'id')
        .iterator()
    ):
        if ipv.item_proposta_id not in links:
            links[ipv.item_proposta_id] = ipv

    for item in ItemProposta.objects.all().iterator():
        ipv = links.get(item.pk)
        snapshot = item.snapshot_produto if isinstance(item.snapshot_produto, dict) else {}
        com = snapshot.get('comercial') if isinstance(snapshot.get('comercial'), dict) else {}
        snap_status = (com.get('status_comercial') or '').strip().upper()

        update_fields = ['status_comercial']
        item.status_comercial = STATUS_ITEM_PENDENTE

        if ipv:
            item.status_comercial = STATUS_ITEM_CONVERTIDO
            item.pedido_venda_gerado_id = ipv.pedido_id
            item.item_pedido_venda_gerado_id = ipv.pk
            item.convertido_em = _parse_iso_datetime(com.get('convertido_em')) or timezone.now()
            update_fields.extend(
                ['pedido_venda_gerado_id', 'item_pedido_venda_gerado_id', 'convertido_em'],
            )
        elif snap_status in SNAPSHOT_STATUSES:
            item.status_comercial = snap_status
            if snap_status in (STATUS_ITEM_CANCELADO, STATUS_ITEM_PERDIDO):
                item.cancelado_em = _parse_iso_datetime(com.get('cancelado_em')) or timezone.now()
                update_fields.extend(['cancelado_em'])

        item.save(update_fields=update_fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('comercial', '0032_proposta_campos_comerciais'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposta',
            name='motivo_recuperacao',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='proposta',
            name='recuperada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='proposta',
            name='recuperada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='propostas_recuperadas',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='proposta',
            name='status_anterior_recuperacao',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='cancelado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='cancelado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='itens_proposta_cancelados',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='convertido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='convertido_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='itens_proposta_convertidos',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='motivo_cancelamento_item',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='status_comercial',
            field=models.CharField(
                choices=[
                    ('PENDENTE', 'Pendente'),
                    ('CONVERTIDO_EM_PEDIDO', 'Convertido em pedido'),
                    ('CANCELADO', 'Cancelado'),
                    ('PERDIDO', 'Perdido'),
                    ('MANTIDO_PARA_DEPOIS', 'Mantido para depois'),
                ],
                db_index=True,
                default='PENDENTE',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='item_pedido_venda_gerado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='item_proposta_origem',
                to='comercial.itempedidovenda',
            ),
        ),
        migrations.AddField(
            model_name='itemproposta',
            name='pedido_venda_gerado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='itens_proposta_convertidos',
                to='comercial.pedidovenda',
            ),
        ),
        migrations.CreateModel(
            name='PropostaComercialHistorico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'tipo_evento',
                    models.CharField(
                        choices=[
                            ('PROPOSTA_RECUPERADA', 'Proposta recuperada'),
                            ('PEDIDO_GERADO', 'Pedido de venda gerado'),
                            ('ITEM_CONVERTIDO', 'Item convertido em pedido'),
                            ('ITEM_CANCELADO', 'Item cancelado'),
                            ('ITEM_MANTIDO_PENDENTE', 'Item mantido pendente'),
                        ],
                        max_length=32,
                    ),
                ),
                ('descricao', models.TextField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('dados_json', models.JSONField(blank=True, null=True)),
                (
                    'proposta',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='historico_comercial',
                        to='comercial.proposta',
                    ),
                ),
                (
                    'usuario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='eventos_comerciais_proposta',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Histórico comercial da proposta',
                'verbose_name_plural': 'Históricos comerciais das propostas',
                'ordering': ['-criado_em', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='propostacomercialhistorico',
            index=models.Index(fields=['proposta', '-criado_em'], name='comercial_p_propost_14cd49_idx'),
        ),
        migrations.RunPython(preencher_status_comercial_itens, noop),
    ]
