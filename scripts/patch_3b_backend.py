#!/usr/bin/env python3
"""3b-Backend: proxima_serie + reemitir() + @action reemitir."""
import shutil, sys, pathlib, datetime

# --- 1. numeracao_certificado_qualidade.py: proxima_serie ---
NUM = pathlib.Path("backend/apps/qualidade/services/numeracao_certificado_qualidade.py")
if not NUM.exists():
    sys.exit(f"nao encontrei {NUM}")
num_src = NUM.read_text(encoding="utf-8")
num_orig = num_src

if "def proxima_serie(" not in num_src:
    # Anexa ao final
    num_src += '''

def proxima_serie(serie: str) -> str:
    """Proxima serie alfabetica: ''->A, A->B, ..., Z->AA, AZ->BA, ZZ->AAA."""
    s = (serie or '').strip().upper()
    if not s:
        return 'A'
    chars = list(s)
    i = len(chars) - 1
    while i >= 0:
        if chars[i] < 'Z':
            chars[i] = chr(ord(chars[i]) + 1)
            return ''.join(chars)
        chars[i] = 'A'
        i -= 1
    return 'A' + ''.join(chars)
'''
    num_backup = NUM.with_suffix(f".py.bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copyfile(NUM, num_backup)
    NUM.write_text(num_src, encoding="utf-8")
    print(f"  ok: numeracao_certificado_qualidade.py (+proxima_serie)")
else:
    print(f"  skip: proxima_serie ja existe em {NUM}")

# --- 2. models.py: reemitir() ---
MODELS = pathlib.Path("backend/apps/qualidade/models.py")
if not MODELS.exists():
    sys.exit(f"nao encontrei {MODELS}")
mod_src = MODELS.read_text(encoding="utf-8")
mod_orig = mod_src

if "def reemitir(self)" not in mod_src:
    # Procura o "class CertificadoQualidade(" e injeta antes do proximo class/def
    anchor = "class CertificadoQualidade("
    if anchor not in mod_src:
        sys.exit("nao achei class CertificadoQualidade")
    
    # Inserir metodo no final da classe. Acha proxima class apos o anchor.
    idx = mod_src.index(anchor)
    next_class = mod_src.find("\nclass ", idx + len(anchor))
    if next_class == -1:
        next_class = len(mod_src)
    
    metodo = '''

    def reemitir(self):
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
                    tipo_dados_tecnicos=item_orig.tipo_dados_tecnicos,
                    produto=item_orig.produto,
                    codigo_produto=item_orig.codigo_produto,
                    descricao_material=item_orig.descricao_material,
                    quantidade=item_orig.quantidade,
                    unidade=item_orig.unidade,
                    norma=item_orig.norma,
                    corrida=item_orig.corrida,
                    lote=item_orig.lote,
                    ncm=item_orig.ncm,
                    status_vinculo_produto=item_orig.status_vinculo_produto,
                    produto_snapshot=item_orig.produto_snapshot,
                    produto_codigo=item_orig.produto_codigo,
                    produto_descricao=item_orig.produto_descricao,
                    produto_ncm_efetivo=item_orig.produto_ncm_efetivo,
                    origem_rastreabilidade_tipo=item_orig.origem_rastreabilidade_tipo,
                    origem_status_tecnico=item_orig.origem_status_tecnico,
                    origem_observacoes=item_orig.origem_observacoes,
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
                    incluir_no_certificado=item_orig.incluir_no_certificado,
                    motivo_nao_inclusao=item_orig.motivo_nao_inclusao,
                    observacao_nao_inclusao=item_orig.observacao_nao_inclusao,
                )
                
                for comp_orig in item_orig.componentes.all():
                    ItemCertificadoQualidadeComponente.objects.create(
                        item=item_novo,
                        ordem=comp_orig.ordem,
                        nome_componente=comp_orig.nome_componente,
                        descricao_componente=comp_orig.descricao_componente,
                        norma=comp_orig.norma,
                        corrida=comp_orig.corrida,
                        lote=comp_orig.lote,
                        revisao_corrida=comp_orig.revisao_corrida,
                        numero_certificado_fornecedor_componente=comp_orig.numero_certificado_fornecedor_componente,
                        quantidade=comp_orig.quantidade,
                        composicao_json=dict(comp_orig.composicao_json or {}),
                        ensaio_tracao_json=dict(comp_orig.ensaio_tracao_json or {}),
                        ensaio_impacto_json=dict(comp_orig.ensaio_impacto_json or {}),
                        observacoes=comp_orig.observacoes,
                        ativo=comp_orig.ativo,
                    )
                
                for corr_orig in item_orig.corridas_adicionais.all():
                    ItemCertificadoQualidadeCorrida.objects.create(
                        item=item_novo,
                        corrida=corr_orig.corrida,
                        lote=corr_orig.lote,
                        quantidade=corr_orig.quantidade,
                    )
            
            self.substituido_por = novo
            self.status = CertificadoQualidade.Status.SUBSTITUIDO
            self.save(update_fields=['substituido_por', 'status'])
        
        return novo
'''
    
    mod_src = mod_src[:next_class] + metodo + mod_src[next_class:]
    mod_backup = MODELS.with_suffix(f".py.bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copyfile(MODELS, mod_backup)
    MODELS.write_text(mod_src, encoding="utf-8")
    print(f"  ok: models.py (+reemitir)")
else:
    print(f"  skip: reemitir ja existe")

# --- 3. views.py: @action reemitir ---
VIEWS = pathlib.Path("backend/apps/qualidade/views.py")
if not VIEWS.exists():
    sys.exit(f"nao encontrei {VIEWS}")
view_src = VIEWS.read_text(encoding="utf-8")

if "url_path='reemitir'" not in view_src:
    # Ancorar no final do preencher_por_nfe ou outro action. Vou ancorar antes do proximo @action
    # Melhor: ancorar no ultimo @action (buscar-dados-tecnicos) - achar o final do metodo
    # Simplificacao: inserir apos a definicao da classe e o get_queryset
    anchor = "    @action(detail=False, methods=['get'], url_path='nfes-elegiveis')"
    if anchor not in view_src:
        sys.exit("nao achei anchor nfes-elegiveis")
    
    action = '''    @action(detail=True, methods=['post'], url_path='reemitir')
    def reemitir(self, request, pk=None):
        """Cria novo CQ clonando este, incrementa serie e marca este como substituido."""
        cq = self.get_object()
        if cq.status != CertificadoQualidade.Status.EMITIDO:
            return Response(
                {'detail': 'Somente certificados emitidos podem ser reemitidos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        novo = cq.reemitir()
        serializer = self.get_serializer(novo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

'''
    view_src = view_src.replace(anchor, action + anchor, 1)
    view_backup = VIEWS.with_suffix(f".py.bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copyfile(VIEWS, view_backup)
    VIEWS.write_text(view_src, encoding="utf-8")
    print(f"  ok: views.py (+@action reemitir)")
else:
    print(f"  skip: @action reemitir ja existe")

print("\nOK. Rode:")
print("  cd backend && python3 -c \"import ast,pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('apps/qualidade').rglob('*.py')]; print('ast ok')\"")
print("  python3 manage.py check")
