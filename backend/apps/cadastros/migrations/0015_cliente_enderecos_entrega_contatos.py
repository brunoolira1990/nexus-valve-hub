from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0014_cliente_ie_isento'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnderecoEntregaCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identificacao', models.CharField(blank=True, help_text='Apelido para diferenciar endereços (ex.: Filial Campinas).', max_length=120)),
                ('cep', models.CharField(blank=True, max_length=16)),
                ('logradouro', models.CharField(blank=True, max_length=255)),
                ('numero', models.CharField(blank=True, max_length=32)),
                ('complemento', models.CharField(blank=True, max_length=128)),
                ('bairro', models.CharField(blank=True, max_length=128)),
                ('cidade', models.CharField(blank=True, max_length=128)),
                ('uf', models.CharField(blank=True, max_length=2)),
                ('principal', models.BooleanField(default=False, help_text='Endereço de entrega padrão quando houver mais de um.')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enderecos_entrega', to='cadastros.cliente')),
            ],
            options={
                'verbose_name': 'Endereço de entrega do cliente',
                'verbose_name_plural': 'Endereços de entrega do cliente',
                'ordering': ['-principal', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ContatoCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('COMERCIAL', 'Comercial'), ('FINANCEIRO', 'Financeiro'), ('TECNICO', 'Técnico'), ('OUTRO', 'Outro')], default='COMERCIAL', max_length=16)),
                ('nome', models.CharField(blank=True, max_length=255)),
                ('telefone', models.CharField(blank=True, max_length=32)),
                ('celular', models.CharField(blank=True, max_length=32)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('principal', models.BooleanField(default=False, help_text='Contato principal dentro do mesmo tipo.')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contatos', to='cadastros.cliente')),
            ],
            options={
                'verbose_name': 'Contato do cliente',
                'verbose_name_plural': 'Contatos do cliente',
                'ordering': ['tipo', '-principal', 'id'],
            },
        ),
    ]
