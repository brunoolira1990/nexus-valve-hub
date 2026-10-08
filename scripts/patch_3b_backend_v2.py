#!/usr/bin/env python3
"""3b-backend v2: corrige reemitir() com os nomes reais dos campos + serie A no create."""
import shutil, sys, pathlib, datetime, re

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# ============ 1. Reescrever reemitir() no models.py ============
MODELS = pathlib.Path("backend/apps/qualidade/models.py")
src = MODELS.read_text(encoding="utf-8")

# Localiza o bloco reemitir (do "    def reemitir(self):" até o proximo "    def " ou classe)
pattern = re.compile(
    r"    def reemitir\(self\):.*?(?=\n    def |\nclass |\Z)",
    re.DOTALL,
)
m = pattern.search(src)
if not m:
    sys.exit("nao achei o metodo reemitir()")

NOVO_METODO = '''    def reemitir(self):
        """Cria um novo CQ clonando este (itens + componentes + corridas), incrementa serie,
        e marca este como SUBSTITUIDO apontando para o novo.

        Retorna o novo CertificadoQualidade (status RASCUNHO).
        """
        from django.db import transaction
        from apps.qualidade.services.numeracao_certificado_qualidade import (
            proxima_serie,
            gerar_numero_certificado_qualidade,
        )
        from apps.qualidade.models import (
            ItemCertificadoQualidade,
            ItemCertificadoQualidadeComponente,
            ItemCertificadoQualidadeCorrida,
        )

        with transaction.atomic():
            novo = CertificadoQualidade.objects.create(
                numero=gerar_numero_certificado_qualidade(),
                serie=proxima_serie(self.serie),
                cliente=self.cliente,
                cliente_nome_snapshot=self.cliente_nome_snapshot,
                cliente_cnpj_snapshot=self.cliente_cnpj_snapshot,
                pedido_cliente=self.pedido_cliente,
                nota_fiscal_numero=self.nota_fiscal_numero,
                nota_fiscal=self.nota_fiscal,
                nota_fiscal_historica=self.nota_fiscal_historica,
                data_emissao=self.data_emissao,
                observacoes=self.observacoes,
                texto_padrao=self.texto_padrao,
                status=CertificadoQualidade.Status.RASCUNHO,
                tipo_certificado=self.tipo_certificado,
            )

            for item_orig in self.itens.all():
                item_novo = ItemCertificadoQualidade.objects.create(
                    certificado=novo,
                    ordem=item_orig.ordem,
                    produto=item_orig.produto,
                    codigo_produto=item_orig.codigo_produto,
                    descricao_material=item_orig.descricao_material,
                    quantidade=item_orig.quantidade,
                    unidade=item_orig.unidade,
                    norma=item_orig.norma,
                    corrida=item_orig.corrida,
                    lote=item_orig.lote,
                    tipo_dados_tecnicos=item_orig.tipo_dados_tecnicos,
                    ncm=item_orig.ncm,
                    observacoes_item=item_orig.observacoes_item,
                    composicao_json=dict(item_orig.composicao_json or {}),
                    ensaio_tracao_json=dict(item_orig.ensaio_tracao_json or {}),
                    ensaio_impacto_json=dict(item_orig.ensaio_impacto_json or {}),
                    certificado_fornecedor_origem_id=item_orig.certificado_fornecedor_origem_id,
                    item_certificado_fornecedor_origem_id=item_orig.item_certificado_fornecedor_origem_id,
                    fornecedor_nome_snapshot=item_orig.fornecedor_nome_snapshot,
                    nf_entrada_snapshot=item_orig.nf_entrada_snapshot,
                    codigo_item_fornecedor_snapshot=item_orig.codigo_item_fornecedor_snapshot,
                    descricao_item_fornecedor_snapshot=item_orig.descricao_item_fornecedor_snapshot,
                    numero_certificado_fornecedor_item_snapshot=item_orig.numero_certificado_fornecedor_item_snapshot,
                    corrida_snapshot=item_orig.corrida_snapshot,
                    lote_snapshot=item_orig.lote_snapshot,
                    produto_snapshot=dict(item_orig.produto_snapshot or {}),
                    origem_rastreabilidade_tipo=item_orig.origem_rastreabilidade_tipo,
                    origem_status_tecnico=item_orig.origem_status_tecnico,
                    origem_observacoes=item_orig.origem_observacoes,
                    incluir_no_certificado=item_orig.incluir_no_certificado,
                    motivo_nao_inclusao=item_orig.motivo_nao_inclusao,
                    observacao_nao_inclusao=item_orig.observacao_nao_inclusao,
                )

                for comp_orig in item_orig.componentes.all():
                    ItemCertificadoQualidadeComponente.objects.create(
                        item_certificado=item_novo,
                        ordem=comp_orig.ordem,
                        nome_componente=comp_orig.nome_componente,
                        descricao_componente=comp_orig.descricao_componente,
                        norma=comp_orig.norma,
                        corrida=comp_orig.corrida,
                        revisao_corrida=comp_orig.revisao_corrida,
                        numero_certificado_fornecedor_componente_snapshot=comp_orig.numero_certificado_fornecedor_componente_snapshot,
                        quantidade=comp_orig.quantidade,
                        composicao_json=dict(comp_orig.composicao_json or {}),
                        ensaio_tracao_json=dict(comp_orig.ensaio_tracao_json or {}),
                        ensaio_impacto_json=dict(comp_orig.ensaio_impacto_json or {}),
                        observacoes=comp_orig.observacoes,
                        ativo=comp_orig.ativo,
                    )

                for corr_orig in item_orig.corridas_adicionais.all():
                    ItemCertificadoQualidadeCorrida.objects.create(
                        item_certificado=item_novo,
                        ordem=corr_orig.ordem,
                        corrida=corr_orig.corrida,
                        lote=corr_orig.lote,
                        quantidade=corr_orig.quantidade,
                        composicao_json=dict(corr_orig.composicao_json or {}),
                        ensaio_tracao_json=dict(corr_orig.ensaio_tracao_json or {}),
                        ensaio_impacto_json=dict(corr_orig.ensaio_impacto_json or {}),
                    )

            self.substituido_por = novo
            self.status = CertificadoQualidade.Status.SUBSTITUIDO
            self.save(update_fields=['substituido_por', 'status'])

        return novo
'''

src = src[:m.start()] + NOVO_METODO + src[m.end():]
shutil.copyfile(MODELS, MODELS.with_suffix(f".py.bak_{stamp}"))
MODELS.write_text(src, encoding="utf-8")
print("  ok: models.py — reemitir() reescrito")

# ============ 2. Serie='A' no create ============
SER = pathlib.Path("backend/apps/qualidade/serializers.py")
s = SER.read_text(encoding="utf-8")

old = (
    "        if numero_certificado_qualidade_vazio(validated_data.get('numero')):\n"
    "            validated_data['numero'] = gerar_numero_certificado_qualidade()\n"
    "        obj = CertificadoQualidade.objects.create(**validated_data)\n"
)
new = (
    "        if numero_certificado_qualidade_vazio(validated_data.get('numero')):\n"
    "            validated_data['numero'] = gerar_numero_certificado_qualidade()\n"
    "        # Serie inicial sempre 'A' (primeira versao antes de reemissao)\n"
    "        if not (validated_data.get('serie') or '').strip():\n"
    "            validated_data['serie'] = 'A'\n"
    "        obj = CertificadoQualidade.objects.create(**validated_data)\n"
)
if s.count(old) == 1:
    s = s.replace(old, new, 1)
    shutil.copyfile(SER, SER.with_suffix(f".py.bak_{stamp}"))
    SER.write_text(s, encoding="utf-8")
    print("  ok: serializers.py — serie=A no create")
elif "validated_data['serie'] = 'A'" in s:
    print("  skip: serie=A ja existe")
else:
    sys.exit("nao achei o bloco do create pra serie A")

print("\nOK. Rode:")
print("  cd backend && python3 manage.py check")
