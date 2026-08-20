from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='external_id',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='pagina_origem',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='lead',
            name='produto_interesse',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='lead',
            name='utm_campaign',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='lead',
            name='utm_content',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='lead',
            name='utm_medium',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='lead',
            name='utm_source',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='lead',
            name='utm_term',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(
                fields=['origem', 'status', '-atualizado_em'],
                name='crm_lead_origin_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(
                fields=['utm_campaign', '-atualizado_em'],
                name='crm_lead_campaign_updated_idx',
            ),
        ),
    ]
