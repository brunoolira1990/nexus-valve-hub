"""Serializers de auditoria com resolução de FKs e enums no momento da leitura.

O diff é gravado cru (ids de FK, strings legadas, códigos de enum). Para exibir
histórico legível sem reescrever registros antigos, o valor é enriquecido aqui:
`{antes, depois}` passa a ser `{valor, id, nome}` quando houver correspondência.
"""

from __future__ import annotations

import unicodedata

from django.apps import apps as django_apps
from rest_framework import serializers

from apps.auditoria.models import RegistroAuditoria
from apps.produtos.material import material_label_de_valor
from apps.produtos.rotulos import nome_familia_produto

# Campo auditado -> (app_label, model, atributo usado como rótulo).
FKS_AUDITADAS: dict[str, tuple[str, str, str]] = {
    'familia_id': ('produtos', 'FamiliaProduto', 'descricao_base'),
    'transportadora_padrao_id': ('cadastros', 'Transportadora', 'razao_social'),
}

CAMPO_MATERIAL_LEGADO = 'material'


def _normalizar_texto(valor) -> str:
    """Sem acentos e sem caixa: 'AÇO CARBONO' e 'ACO CARBONO' são o mesmo material."""
    texto = unicodedata.normalize('NFKD', str(valor or ''))
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    return ' '.join(texto.split()).strip().upper()


class EnriquecedorValores:
    """Resolve em lote os valores de uma página de registros de auditoria."""

    def __init__(self, app_label: str, model_name: str):
        self.app_label = app_label
        self.model_name = model_name
        self._fk: dict[str, dict] = {}
        self._fk_ids: dict[str, list] = {}
        self._materiais_textos: list[str] = []
        self._materiais: dict = {}
        self._escolhas: dict[str, dict] = {}

    # ---------------- coleta ----------------

    def coletar(self, alteracoes: dict) -> None:
        for campo, alt in (alteracoes or {}).items():
            if not isinstance(alt, dict):
                continue
            if campo in FKS_AUDITADAS:
                coletados = self._fk_ids.setdefault(campo, [])
                for chave in ('antes', 'depois'):
                    valor = alt.get(chave)
                    if isinstance(valor, int) and valor not in coletados:
                        coletados.append(valor)
            elif campo == CAMPO_MATERIAL_LEGADO:
                for chave in ('antes', 'depois'):
                    valor = alt.get(chave)
                    if isinstance(valor, str) and valor.strip() and valor not in self._materiais_textos:
                        self._materiais_textos.append(valor)

    # ---------------- carregamento ----------------

    def carregar(self) -> None:
        for campo, ids in self._fk_ids.items():
            destino = FKS_AUDITADAS.get(campo)
            if not ids or destino is None:
                continue
            app_label, nome_modelo, atributo = destino
            modelo = django_apps.get_model(app_label, nome_modelo)
            self._fk[campo] = {
                obj.pk: self._rotulo_modelo(obj, nome_modelo, atributo)
                for obj in modelo.objects.filter(pk__in=ids)
            }
        if self._materiais_textos:
            self._materiais = self._carregar_materiais(self._materiais_textos)

    def _rotulo_modelo(self, obj, nome_modelo: str, atributo: str) -> str:
        if nome_modelo == 'FamiliaProduto':
            return nome_familia_produto(obj)
        return str(getattr(obj, atributo, '') or '').strip() or str(obj)

    def _carregar_materiais(self, textos: list) -> dict:
        Material = django_apps.get_model('produtos', 'Material')
        por_texto: dict = {}
        for material in Material.objects.all():
            chaves = {
                _normalizar_texto(material.nome),
                _normalizar_texto(material.nome_curto),
                _normalizar_texto(material.codigo),
            }
            for alias in material.aliases or []:
                chaves.add(_normalizar_texto(alias))
            entrada = {'id': material.pk, 'nome': material.nome}
            for chave in chaves:
                if chave:
                    por_texto.setdefault(chave, entrada)
        resolvidos: dict = {}
        for texto in textos:
            entrada = por_texto.get(_normalizar_texto(texto))
            if entrada is not None:
                resolvidos[texto] = entrada
        return resolvidos

    # ---------------- enums ----------------

    def _mapa_escolhas(self, campo: str) -> dict:
        if campo in self._escolhas:
            return self._escolhas[campo]
        mapa: dict = {}
        try:
            modelo = django_apps.get_model(self.app_label, self.model_name)
            campo_modelo = modelo._meta.get_field(campo)
        except LookupError:
            campo_modelo = None
        if campo_modelo is not None and getattr(campo_modelo, 'choices', None):
            mapa = {str(valor): str(rotulo) for valor, rotulo in campo_modelo.choices}
        self._escolhas[campo] = mapa
        return mapa

    # ---------------- saída ----------------

    def _resolver(self, campo: str, valor):
        if valor is None or isinstance(valor, (bool, list, dict)):
            return None
        if campo in FKS_AUDITADAS:
            nome = self._fk.get(campo, {}).get(valor)
            if nome:
                return {'valor': valor, 'id': valor, 'nome': nome}
            return None
        if campo == CAMPO_MATERIAL_LEGADO:
            entrada = self._materiais.get(valor)
            if entrada is not None:
                return {'valor': valor, 'id': entrada['id'], 'nome': entrada['nome']}
            # 'ACO CARBONO' e 'LATAO' são categorias do formulário, não nomes do catálogo.
            rotulo = material_label_de_valor(valor)
            if rotulo and rotulo != valor:
                return {'valor': valor, 'id': None, 'nome': rotulo}
            return None
        rotulo = self._mapa_escolhas(campo).get(str(valor))
        if rotulo and rotulo != valor:
            return {'valor': valor, 'id': None, 'nome': rotulo}
        return None

    def enriquecer(self, alteracoes: dict) -> dict:
        saida: dict = {}
        for campo, alt in (alteracoes or {}).items():
            if not isinstance(alt, dict):
                saida[campo] = alt
                continue
            novo = dict(alt)
            for chave in ('antes', 'depois'):
                if chave not in alt:
                    continue
                resolvido = self._resolver(campo, alt[chave])
                if resolvido is not None:
                    novo[chave] = resolvido
            saida[campo] = novo
        return saida


class AtorAuditoriaSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    nome = serializers.CharField(allow_null=True)


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    ator = serializers.SerializerMethodField()
    alteracoes = serializers.SerializerMethodField()

    class Meta:
        model = RegistroAuditoria
        fields = ('id', 'operacao', 'ator', 'criado_em', 'alteracoes')
        read_only_fields = fields

    def get_ator(self, obj: RegistroAuditoria) -> dict:
        user = obj.ator
        if user is None:
            return {'id': None, 'nome': None}
        nome = (user.get_full_name() or '').strip() or user.get_username()
        return {'id': user.pk, 'nome': nome}

    def get_alteracoes(self, obj: RegistroAuditoria) -> dict:
        enriquecedor = self.context.get('enriquecedor')
        if enriquecedor is None:
            enriquecedor = EnriquecedorValores(obj.app_label, obj.model_name)
            enriquecedor.coletar(obj.alteracoes)
            enriquecedor.carregar()
        return enriquecedor.enriquecer(obj.alteracoes)


def enriquecedor_para(registros: list[RegistroAuditoria]) -> EnriquecedorValores | None:
    """Um único enriquecedor por página: a view só serve histórico de um objeto, então o par app/model é fixo."""
    if not registros:
        return None
    enriquecedor = EnriquecedorValores(registros[0].app_label, registros[0].model_name)
    for registro in registros:
        enriquecedor.coletar(registro.alteracoes)
    enriquecedor.carregar()
    return enriquecedor
