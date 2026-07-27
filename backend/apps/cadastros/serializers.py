from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.auditoria.servico import (
    registrar_cliente,
    snapshot_cliente,
    usuario_do_contexto,
)
from apps.comercial.payment_terms import parse_payment_condition
from apps.text_normalize import normalize_operational_fields

from .colaborador_acesso import montar_acesso_colaborador, PERFIS_DISPONIVEIS
from .colaborador_senha import email_operacional_valido, usuario_eh_admin
from .colaborador_sync import sincronizar_vendedor_colaborador, vendedor_id_colaborador
from .colaborador_usuario import validar_usuario_colaborador_unico
from .cliente_nested_sync import sincronizar_contatos_cliente, sincronizar_enderecos_entrega
from .contato_cliente_email import (
    MSG_EMAIL_DUPLICADO,
    MSG_EMAIL_FISCAL_OBRIGATORIO,
    MSG_EMAIL_INVALIDO,
    chave_email_contato,
    normalizar_email_contato,
    tem_erros_por_contato,
    validar_unicidade_emails_contatos_payload,
)
from .models import (
    Cliente,
    Colaborador,
    ContatoCliente,
    Empresa,
    EnderecoEntregaCliente,
    Fornecedor,
    Transportadora,
)


class EmpresaSerializer(serializers.ModelSerializer):
    empresa_pai_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source='empresa_pai',
        allow_null=True,
        required=False,
    )
    nfe_producao_habilitada = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Empresa
        exclude = ('empresa_pai',)
        extra_kwargs = {
            'senha_certificado': {'write_only': True, 'required': False, 'allow_blank': True},
        }
        read_only_fields = ('nfe_producao_habilitada',)

    def get_nfe_producao_habilitada(self, obj) -> bool:
        return bool(getattr(settings, 'NFE_PRODUCAO_HABILITADA', False))

    def validate_nfe_ambiente(self, value):
        valor = (value or '').strip().lower()
        validos = {c[0] for c in Empresa.NfeAmbiente.choices}
        if valor not in validos:
            raise serializers.ValidationError('Ambiente NF-e inválido. Use homologacao ou producao.')
        return valor

    def validate(self, attrs):
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'im',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'telefone',
            },
        )
        pai = attrs.get('empresa_pai')
        pk = self.instance.pk if self.instance else None
        if pk and pai and pai.pk == pk:
            raise serializers.ValidationError(
                {'empresa_pai_id': 'A empresa não pode ser filial de si mesma.'}
            )
        return attrs

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if getattr(e, 'message_dict', None) else e.messages
            ) from e

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                e.message_dict if getattr(e, 'message_dict', None) else e.messages
            ) from e

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['empresa_pai_id'] = instance.empresa_pai_id
        request = self.context.get('request')
        if request:
            if instance.certificado_arquivo:
                data['certificado_arquivo'] = request.build_absolute_uri(
                    instance.certificado_arquivo.url
                )
            if instance.logotipo:
                data['logotipo'] = request.build_absolute_uri(instance.logotipo.url)
        return data


class EnderecoEntregaClienteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = EnderecoEntregaCliente
        fields = (
            'id',
            'identificacao',
            'cep',
            'logradouro',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'uf',
            'principal',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'identificacao',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
            },
        )
        return attrs


class ContatoClienteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        error_messages={'invalid': MSG_EMAIL_INVALIDO},
    )
    ativo = serializers.BooleanField(required=False, default=True)
    recebe_documentos_fiscais = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = ContatoCliente
        fields = (
            'id',
            'tipo',
            'nome',
            'telefone',
            'celular',
            'email',
            'principal',
            'ativo',
            'recebe_documentos_fiscais',
        )

    def validate_tipo(self, value):
        valor = (value or '').strip().upper()
        validos = {c[0] for c in ContatoCliente.Tipo.choices}
        if valor not in validos:
            raise serializers.ValidationError('Tipo de contato inválido.')
        return valor

    def validate_email(self, value):
        return normalizar_email_contato(value)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'nome'})
        email = normalizar_email_contato(
            attrs.get(
                'email',
                getattr(self.instance, 'email', '') if self.instance else '',
            )
        )
        if 'email' in attrs:
            attrs['email'] = email
        recebe = attrs.get(
            'recebe_documentos_fiscais',
            getattr(self.instance, 'recebe_documentos_fiscais', False) if self.instance else False,
        )
        if recebe and not email:
            raise serializers.ValidationError({'email': MSG_EMAIL_FISCAL_OBRIGATORIO})
        return attrs


class ClienteSerializer(serializers.ModelSerializer):
    transportadora_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora_padrao',
        allow_null=True,
        required=False,
    )
    enderecos_entrega = EnderecoEntregaClienteSerializer(many=True, required=False)
    contatos = ContatoClienteSerializer(many=True, required=False)

    class Meta:
        model = Cliente
        exclude = ('transportadora_padrao',)

    def _normalizar_principais_enderecos(self, items: list[dict]) -> list[dict]:
        principal_idx = next((i for i, item in enumerate(items) if item.get('principal')), None)
        if principal_idx is None and items:
            items[0]['principal'] = True
            return items
        for i, item in enumerate(items):
            item['principal'] = i == principal_idx
        return items

    def _normalizar_principais_contatos(self, items: list[dict]) -> list[dict]:
        por_tipo: dict[str, list[int]] = {}
        for i, item in enumerate(items):
            tipo = (item.get('tipo') or ContatoCliente.Tipo.COMERCIAL).strip().upper()
            item['tipo'] = tipo
            por_tipo.setdefault(tipo, []).append(i)
        for indices in por_tipo.values():
            principal_idx = next((i for i in indices if items[i].get('principal')), indices[0])
            for i in indices:
                items[i]['principal'] = i == principal_idx
        return items

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'contato_responsavel',
                'observacoes',
                'informacoes_complementares_nfe',
                'inscricao_municipal',
                'suframa',
                'vendedor_padrao',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
                'cnae',
                'regime_tributario',
                'integracao_texto',
                'condicao_pagamento_texto',
            },
        )
        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        ie_isento = attrs.get('ie_isento', self.instance.ie_isento if self.instance else False)
        if ie_isento:
            attrs['ie_isento'] = True
            attrs['ie'] = ''
        enderecos = attrs.get('enderecos_entrega')
        if enderecos is not None:
            attrs['enderecos_entrega'] = self._normalizar_principais_enderecos(enderecos)
        contatos = attrs.get('contatos')
        if contatos is not None:
            contatos = self._normalizar_principais_contatos(contatos)
            self._validar_emails_contatos(contatos)
            attrs['contatos'] = contatos
        return attrs

    def _validar_emails_contatos(self, contatos: list[dict]) -> None:
        """Unicidade case-insensitive no payload e contra contatos que permanecerão no cliente."""
        erros = validar_unicidade_emails_contatos_payload(contatos)
        cliente = self.instance
        if cliente is not None and cliente.pk:
            ids_no_payload: set[int] = set()
            for item in contatos:
                pk = item.get('id')
                if pk is None:
                    continue
                try:
                    ids_no_payload.add(int(pk))
                except (TypeError, ValueError):
                    continue

            emails_payload_por_id: dict[int, str] = {}
            for item in contatos:
                pk = item.get('id')
                if pk is None:
                    continue
                try:
                    emails_payload_por_id[int(pk)] = chave_email_contato(item.get('email'))
                except (TypeError, ValueError):
                    continue

            persistidos = {
                c.pk: chave_email_contato(c.email)
                for c in cliente.contatos.all()
            }

            for i, item in enumerate(contatos):
                chave = chave_email_contato(item.get('email'))
                if not chave or 'email' in erros[i]:
                    continue
                own_id = item.get('id')
                try:
                    own_id_int = int(own_id) if own_id is not None else None
                except (TypeError, ValueError):
                    own_id_int = None

                for pk, chave_db in persistidos.items():
                    if chave_db != chave:
                        continue
                    if own_id_int is not None and pk == own_id_int:
                        continue
                    # Contato persistido fora do payload será removido no sync — não conflita.
                    if pk not in ids_no_payload:
                        continue
                    # Fonte de verdade do e-mail do persistido que permanece: o próprio payload.
                    chave_no_payload = emails_payload_por_id.get(pk, '')
                    if chave_no_payload == chave:
                        erros[i]['email'] = [MSG_EMAIL_DUPLICADO]
                        break

        if tem_erros_por_contato(erros):
            raise serializers.ValidationError({'contatos': erros})

    def create(self, validated_data):
        enderecos = validated_data.pop('enderecos_entrega', [])
        contatos = validated_data.pop('contatos', [])
        usuario = usuario_do_contexto(self)
        with transaction.atomic():
            cliente = super().create(validated_data)
            if enderecos:
                sincronizar_enderecos_entrega(cliente, enderecos)
            if contatos:
                sincronizar_contatos_cliente(cliente, contatos)
            registrar_cliente(
                usuario=usuario,
                cliente=cliente,
                operacao='CREATE',
                estado_anterior={},
                estado_posterior=snapshot_cliente(cliente),
            )
            return cliente

    def update(self, instance, validated_data):
        enderecos = validated_data.pop('enderecos_entrega', None)
        contatos = validated_data.pop('contatos', None)
        usuario = usuario_do_contexto(self)
        antes = snapshot_cliente(instance)
        with transaction.atomic():
            cliente = super().update(instance, validated_data)
            if enderecos is not None:
                sincronizar_enderecos_entrega(cliente, enderecos)
            if contatos is not None:
                sincronizar_contatos_cliente(cliente, contatos)
            registrar_cliente(
                usuario=usuario,
                cliente=cliente,
                operacao='UPDATE',
                estado_anterior=antes,
                estado_posterior=snapshot_cliente(cliente),
            )
            return cliente

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['transportadora_padrao_id'] = instance.transportadora_padrao_id
        from apps.cadastros.endereco_fiscal import serializar_endereco_fiscal_cliente

        data['endereco_fiscal'] = serializar_endereco_fiscal_cliente(instance, consultar_cep=False)
        return data


class FornecedorSerializer(serializers.ModelSerializer):
    transportadora_padrao_id = serializers.PrimaryKeyRelatedField(
        queryset=Transportadora.objects.all(),
        source='transportadora_padrao',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Fornecedor
        exclude = ('transportadora_padrao',)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'contato_responsavel',
                'observacoes',
                'inscricao_municipal',
                'suframa',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
                'cnae',
                'regime_tributario',
                'integracao_texto',
                'condicao_pagamento_texto',
            },
        )
        texto = attrs.get(
            'condicao_pagamento_texto',
            self.instance.condicao_pagamento_texto if self.instance else '',
        )
        dias = parse_payment_condition(texto)
        attrs['dias_parcelas'] = dias
        attrs['quantidade_parcelas'] = len(dias)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['transportadora_padrao_id'] = instance.transportadora_padrao_id
        return data


class TransportadoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transportadora
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(
            attrs,
            {
                'razao_social',
                'nome_fantasia',
                'ie',
                'inscricao_municipal',
                'logradouro',
                'numero',
                'complemento',
                'bairro',
                'cidade',
                'uf',
                'contato',
                'placa_padrao',
                'uf_placa',
                'observacoes',
                'ddd',
                'suframa',
                'banco',
                'agencia',
                'conta',
                'tipo_conta',
                'cnae',
                'regime_tributario',
                'integracao_texto',
            },
        )
        return attrs


class CriarUsuarioColaboradorSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    nome = serializers.CharField(max_length=255)
    perfil = serializers.CharField(max_length=32)
    ativo = serializers.BooleanField(required=False, default=True)
    senha = serializers.CharField(write_only=True, trim_whitespace=False)
    confirmar_senha = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        if not email_operacional_valido(value):
            raise serializers.ValidationError('Informe um e-mail válido.')
        return value.strip()

    def validate_nome(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError('Informe o nome do usuário.')
        return v

    def validate_perfil(self, value):
        v = (value or '').strip().lower()
        if not v:
            raise serializers.ValidationError('Selecione um perfil de acesso.')
        if v not in PERFIS_DISPONIVEIS:
            raise serializers.ValidationError('Perfil de acesso inválido.')
        return v

    def validate(self, attrs):
        attrs = super().validate(attrs)
        from apps.core.usuario_exibicao import email_eh_tecnico_local

        if attrs.get('ativo', True) and email_eh_tecnico_local(attrs.get('email', '')):
            raise serializers.ValidationError({'email': 'Informe um e-mail válido para produção.'})
        senha = attrs.get('senha') or ''
        conf = attrs.get('confirmar_senha') or ''
        if not senha.strip():
            raise serializers.ValidationError({'senha': 'Informe a senha.'})
        if not conf.strip():
            raise serializers.ValidationError({'confirmar_senha': 'Confirme a senha.'})
        if senha != conf:
            raise serializers.ValidationError({'confirmar_senha': 'As senhas informadas não conferem.'})
        return attrs


class RedefinirSenhaColaboradorSerializer(serializers.Serializer):
    nova_senha = serializers.CharField(write_only=True, trim_whitespace=False)
    confirmar_senha = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['nova_senha'] != attrs['confirmar_senha']:
            raise serializers.ValidationError({'confirmar_senha': 'As senhas informadas não conferem.'})
        return attrs


class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(write_only=True, trim_whitespace=False)
    nova_senha = serializers.CharField(write_only=True, trim_whitespace=False)
    confirmar_senha = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['nova_senha'] != attrs['confirmar_senha']:
            raise serializers.ValidationError({'confirmar_senha': 'Nova senha e confirmação não conferem.'})
        return attrs


class DefinirPerfilAcessoSerializer(serializers.Serializer):
    perfil = serializers.CharField(max_length=32)

    def validate_perfil(self, value):
        v = (value or '').strip().lower()
        if not v:
            raise serializers.ValidationError('Selecione um perfil de acesso.')
        if v not in PERFIS_DISPONIVEIS:
            raise serializers.ValidationError('Perfil de acesso inválido.')
        return v


class EditarAcessoColaboradorSerializer(serializers.Serializer):
    ativo = serializers.BooleanField(required=False)
    email = serializers.CharField(required=False, allow_blank=True, max_length=254)
    perfil = serializers.CharField(required=False, allow_blank=True, max_length=32)
    is_staff = serializers.BooleanField(required=False)
    is_superuser = serializers.BooleanField(required=False)

    def validate_email(self, value):
        return (value or '').strip()

    def validate_perfil(self, value):
        v = (value or '').strip().lower()
        if not v:
            return ''
        if v not in PERFIS_DISPONIVEIS:
            raise serializers.ValidationError('Perfil de acesso inválido.')
        return v


class VincularUsuarioColaboradorSerializer(serializers.Serializer):
    usuario_id = serializers.IntegerField()
    perfil = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        perfil = (attrs.get('perfil') or '').strip().lower()
        if perfil and perfil not in PERFIS_DISPONIVEIS:
            raise serializers.ValidationError({'perfil': 'Perfil de acesso inválido.'})
        attrs['perfil'] = perfil or None
        user = get_user_model().objects.filter(pk=attrs['usuario_id']).first()
        if not user:
            raise serializers.ValidationError({'usuario_id': 'Usuário não encontrado.'})
        if not user.is_superuser and not user.groups.exists() and not attrs['perfil']:
            raise serializers.ValidationError(
                {'perfil': 'Selecione um perfil de acesso para o usuário vinculado.'},
            )
        attrs['usuario'] = user
        return attrs


class ColaboradorSerializer(serializers.ModelSerializer):
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all(),
        source='usuario',
        allow_null=True,
        required=False,
    )
    perfil_acesso_vinculo = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=32,
        help_text='Perfil ao vincular usuário existente sem grupo.',
    )
    vendedor_id = serializers.SerializerMethodField(read_only=True)
    usuario_login = serializers.SerializerMethodField(read_only=True)
    usuario_email = serializers.SerializerMethodField(read_only=True)
    usuario_username = serializers.SerializerMethodField(read_only=True)
    usuario_ativo = serializers.SerializerMethodField(read_only=True)
    usuario_is_staff = serializers.SerializerMethodField(read_only=True)
    usuario_is_superuser = serializers.SerializerMethodField(read_only=True)
    usuario_grupos = serializers.SerializerMethodField(read_only=True)
    perfil_acesso = serializers.SerializerMethodField(read_only=True)
    perfil_acesso_label = serializers.SerializerMethodField(read_only=True)
    perfil_sugerido = serializers.SerializerMethodField(read_only=True)
    perfil_sugerido_label = serializers.SerializerMethodField(read_only=True)
    acesso_status = serializers.SerializerMethodField(read_only=True)
    acesso_status_label = serializers.SerializerMethodField(read_only=True)
    status_acesso = serializers.SerializerMethodField(read_only=True)
    pode_criar_usuario = serializers.SerializerMethodField(read_only=True)
    pode_vincular_usuario = serializers.SerializerMethodField(read_only=True)
    pode_desativar_acesso = serializers.SerializerMethodField(read_only=True)
    pode_reenviar_convite = serializers.SerializerMethodField(read_only=True)
    pode_redefinir_senha = serializers.SerializerMethodField(read_only=True)
    pode_definir_perfil = serializers.SerializerMethodField(read_only=True)
    pode_editar_acesso = serializers.SerializerMethodField(read_only=True)
    badge_acesso = serializers.SerializerMethodField(read_only=True)
    sem_perfil = serializers.SerializerMethodField(read_only=True)
    email_tecnico = serializers.SerializerMethodField(read_only=True)
    acesso_sistema = serializers.SerializerMethodField(read_only=True)
    motivo_bloqueio_acesso = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Colaborador
        fields = (
            'id',
            'nome',
            'codigo',
            'email',
            'telefone',
            'cargo',
            'departamento',
            'ativo',
            'usuario_id',
            'perfil_acesso_vinculo',
            'usuario_login',
            'usuario_username',
            'usuario_email',
            'usuario_ativo',
            'usuario_is_staff',
            'usuario_is_superuser',
            'usuario_grupos',
            'perfil_acesso',
            'perfil_acesso_label',
            'perfil_sugerido',
            'perfil_sugerido_label',
            'acesso_status',
            'acesso_status_label',
            'status_acesso',
            'pode_criar_usuario',
            'pode_vincular_usuario',
            'pode_desativar_acesso',
            'pode_reenviar_convite',
            'pode_redefinir_senha',
            'pode_definir_perfil',
            'pode_editar_acesso',
            'badge_acesso',
            'sem_perfil',
            'email_tecnico',
            'acesso_sistema',
            'motivo_bloqueio_acesso',
            'eh_vendedor',
            'eh_comprador',
            'eh_responsavel_fiscal',
            'eh_responsavel_financeiro',
            'eh_responsavel_estoque',
            'eh_responsavel_qualidade',
            'eh_administrador',
            'observacoes',
            'vendedor_id',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = (
            'criado_em',
            'atualizado_em',
            'vendedor_id',
            'usuario_login',
            'usuario_username',
            'usuario_email',
            'usuario_ativo',
            'usuario_is_staff',
            'usuario_is_superuser',
            'usuario_grupos',
            'perfil_acesso',
            'perfil_acesso_label',
            'perfil_sugerido',
            'perfil_sugerido_label',
            'acesso_status',
            'acesso_status_label',
            'status_acesso',
            'pode_criar_usuario',
            'pode_vincular_usuario',
            'pode_desativar_acesso',
            'pode_reenviar_convite',
            'pode_redefinir_senha',
            'pode_definir_perfil',
            'pode_editar_acesso',
            'badge_acesso',
            'sem_perfil',
            'email_tecnico',
            'acesso_sistema',
            'motivo_bloqueio_acesso',
        )

    def _actor(self):
        request = self.context.get('request')
        if request and getattr(request, 'user', None) and request.user.is_authenticated:
            return request.user
        return None

    def _acesso(self, obj):
        if not hasattr(self, '_acesso_cache'):
            self._acesso_cache = {}
        actor = self._actor()
        cache_key = (obj.pk, getattr(actor, 'pk', None))
        if cache_key not in self._acesso_cache:
            self._acesso_cache[cache_key] = montar_acesso_colaborador(obj, actor=actor)
        return self._acesso_cache[cache_key]

    def get_vendedor_id(self, obj):
        return vendedor_id_colaborador(obj)

    def get_usuario_login(self, obj):
        if obj.usuario_id and obj.usuario:
            return obj.usuario.username
        return ''

    def get_usuario_username(self, obj):
        return self.get_usuario_login(obj)

    def get_usuario_email(self, obj):
        if obj.usuario_id and obj.usuario:
            return obj.usuario.email or ''
        return ''

    def get_usuario_ativo(self, obj):
        return self._acesso(obj)['usuario_ativo']

    def get_usuario_is_staff(self, obj):
        return self._acesso(obj)['usuario_is_staff']

    def get_usuario_is_superuser(self, obj):
        return self._acesso(obj)['usuario_is_superuser']

    def get_usuario_grupos(self, obj):
        return self._acesso(obj)['usuario_grupos']

    def get_perfil_acesso(self, obj):
        return self._acesso(obj)['perfil_acesso']

    def get_perfil_acesso_label(self, obj):
        return self._acesso(obj)['perfil_acesso_label']

    def get_perfil_sugerido(self, obj):
        return self._acesso(obj)['perfil_sugerido']

    def get_perfil_sugerido_label(self, obj):
        return self._acesso(obj)['perfil_sugerido_label']

    def get_acesso_status(self, obj):
        return self._acesso(obj)['acesso_status']

    def get_acesso_status_label(self, obj):
        return self._acesso(obj)['acesso_status_label']

    def get_status_acesso(self, obj):
        return self._acesso(obj)['status_acesso']

    def get_pode_criar_usuario(self, obj):
        return self._acesso(obj)['pode_criar_usuario']

    def get_pode_vincular_usuario(self, obj):
        return self._acesso(obj)['pode_vincular_usuario']

    def get_pode_desativar_acesso(self, obj):
        return self._acesso(obj)['pode_desativar_acesso']

    def get_pode_reenviar_convite(self, obj):
        return self._acesso(obj)['pode_reenviar_convite']

    def get_pode_redefinir_senha(self, obj):
        request = self.context.get('request')
        if not request or not usuario_eh_admin(getattr(request, 'user', None)):
            return False
        return self._acesso(obj)['pode_redefinir_senha']

    def get_pode_definir_perfil(self, obj):
        return self._acesso(obj)['pode_definir_perfil']

    def get_pode_editar_acesso(self, obj):
        return self._acesso(obj)['pode_editar_acesso']

    def get_badge_acesso(self, obj):
        return self._acesso(obj)['badge_acesso']

    def get_sem_perfil(self, obj):
        return self._acesso(obj)['sem_perfil']

    def get_email_tecnico(self, obj):
        return self._acesso(obj)['email_tecnico']

    def get_acesso_sistema(self, obj):
        return self._acesso(obj)['acesso_sistema']

    def get_motivo_bloqueio_acesso(self, obj):
        return self._acesso(obj)['motivo_bloqueio_acesso']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        normalize_operational_fields(attrs, {'nome', 'codigo', 'observacoes', 'cargo', 'departamento'})
        instance = getattr(self, 'instance', None)
        perfil_vinculo = (attrs.pop('perfil_acesso_vinculo', None) or '').strip().lower()
        if perfil_vinculo and perfil_vinculo not in PERFIS_DISPONIVEIS:
            raise serializers.ValidationError({'perfil_acesso_vinculo': 'Perfil de acesso inválido.'})
        usuario = attrs.get('usuario')
        if usuario is not None:
            validar_usuario_colaborador_unico(usuario, instance=instance)
            if usuario and not usuario.is_superuser and not usuario.groups.exists() and not perfil_vinculo:
                raise serializers.ValidationError(
                    {
                        'perfil_acesso_vinculo': (
                            'Selecione um perfil de acesso para o usuário vinculado.'
                        ),
                    },
                )
        attrs['_perfil_acesso_vinculo'] = perfil_vinculo or None
        return attrs

    def create(self, validated_data):
        perfil_vinculo = validated_data.pop('_perfil_acesso_vinculo', None)
        colaborador = super().create(validated_data)
        self._aplicar_perfil_vinculo(colaborador, perfil_vinculo)
        sincronizar_vendedor_colaborador(colaborador)
        return colaborador

    def update(self, instance, validated_data):
        perfil_vinculo = validated_data.pop('_perfil_acesso_vinculo', None)
        colaborador = super().update(instance, validated_data)
        self._aplicar_perfil_vinculo(colaborador, perfil_vinculo)
        sincronizar_vendedor_colaborador(colaborador)
        return colaborador

    def _aplicar_perfil_vinculo(self, colaborador, perfil_vinculo):
        if not perfil_vinculo or not colaborador.usuario_id or not colaborador.usuario:
            return
        from apps.cadastros.colaborador_acesso import _aplicar_grupo

        if not colaborador.usuario.is_superuser:
            _aplicar_grupo(colaborador.usuario, perfil_vinculo)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['usuario_id'] = instance.usuario_id
        data['usuario_login'] = self.get_usuario_login(instance)
        data['vendedor_id'] = vendedor_id_colaborador(instance)
        return data
