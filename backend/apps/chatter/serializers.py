from rest_framework import serializers

from .models import AnexoChatter, NotaChatter

# Política de anexo (Sprint 3.15): teto de 10 MB e whitelist de extensões.
# XML/CSV/DOCX/XLSX entram por serem a saída natural do ERP; nada executável.
ANEXO_TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024
ANEXO_EXTENSOES_PERMITIDAS = frozenset(
    {'pdf', 'png', 'jpg', 'jpeg', 'xml', 'csv', 'docx', 'xlsx'}
)


class AnexoChatterSerializer(serializers.ModelSerializer):
    arquivo_url = serializers.SerializerMethodField()
    # `arquivo` só entra (upload); a URL de leitura é `arquivo_url`.
    arquivo = serializers.FileField(write_only=True)

    class Meta:
        model = AnexoChatter
        fields = ('id', 'nota', 'nome_original', 'tamanho_bytes', 'criado_em', 'arquivo', 'arquivo_url')
        read_only_fields = ('id', 'nome_original', 'tamanho_bytes', 'criado_em')

    def validate_arquivo(self, arquivo) -> object:
        nome = getattr(arquivo, 'name', '') or ''
        extensao = nome.rsplit('.', 1)[-1].lower() if '.' in nome else ''
        if extensao not in ANEXO_EXTENSOES_PERMITIDAS:
            permitidas = ', '.join(sorted(ANEXO_EXTENSOES_PERMITIDAS))
            raise serializers.ValidationError(
                f'Tipo de arquivo não permitido. Extensões aceitas: {permitidas}.'
            )
        if arquivo.size > ANEXO_TAMANHO_MAXIMO_BYTES:
            limite_mb = ANEXO_TAMANHO_MAXIMO_BYTES // (1024 * 1024)
            raise serializers.ValidationError(
                f'Arquivo excede o limite de {limite_mb} MB.'
            )
        return arquivo

    def create(self, validated_data):
        arquivo = validated_data['arquivo']
        # Nome e tamanho vêm do upload, nunca do payload: terceiro não pode forjar
        # `tamanho_bytes` nem disfarçar o nome real do arquivo.
        validated_data['nome_original'] = (arquivo.name or '')[:255]
        validated_data['tamanho_bytes'] = arquivo.size
        return super().create(validated_data)

    def get_arquivo_url(self, obj: AnexoChatter) -> str | None:
        if not obj.arquivo:
            return None
        url = obj.arquivo.url
        # MEDIA_URL deste projeto é relativo ('media/'), então o field.url já vem sem
        # barra inicial. Devolver raiz-relativo: absolute_uri resolceria contra a rota
        # /api/chatter/ e o link apontaria para /api/chatter/media/…
        return url if url.startswith(('/', 'http')) else f'/{url}'


class NotaChatterSerializer(serializers.ModelSerializer):
    autor_nome = serializers.SerializerMethodField()
    anexos = AnexoChatterSerializer(many=True, read_only=True)

    class Meta:
        model = NotaChatter
        # entity_type/entity_id são escritos pelo cliente (a nota nasce presa a uma
        # entidade); autor, autor_nome e as datas nascem do request — nunca do payload.
        fields = (
            'id',
            'entity_type',
            'entity_id',
            'texto',
            'autor',
            'autor_nome',
            'anexos',
            'criado_em',
            'atualizado_em',
        )
        read_only_fields = ('id', 'autor', 'autor_nome', 'criado_em', 'atualizado_em')

    def validate_entity_type(self, valor: str) -> str:
        # Normalizada: 'Familia ' e 'familia' não podem virar duas timelines distintas.
        return (valor or '').strip().lower()

    def validate_texto(self, valor: str) -> str:
        texto = (valor or '').strip()
        if not texto:
            raise serializers.ValidationError('A nota não pode ficar vazia.')
        return texto

    def get_autor_nome(self, obj: NotaChatter) -> str | None:
        user = obj.autor
        if user is None:
            return None
        return (user.get_full_name() or '').strip() or user.get_username()
