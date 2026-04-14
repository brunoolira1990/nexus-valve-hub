from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.apuracao_fiscal.views import ApuracaoView
from apps.cadastros.views import (
    ClienteViewSet,
    CondicaoPagamentoViewSet,
    EmpresaViewSet,
    FornecedorViewSet,
    TransportadoraViewSet,
)
from apps.comercial.views import PedidoCompraViewSet, PedidoVendaViewSet, PropostaViewSet
from apps.contabil.views import BalanceteView, ContaViewSet, LancamentoViewSet
from apps.corridas.views import CorridaViewSet
from apps.fiscal.views import (
    CTeEntradaViewSet,
    EstoqueViewSet,
    NFeEntradaViewSet,
    NFeSaidaViewSet,
)
from apps.produtos.views import NcmViewSet, PolegadaViewSet, ProdutoViewSet
from apps.qualidade.views import CertificadoViewSet
from apps.regras_fiscais.views import RegraFiscalViewSet

router = DefaultRouter()
router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'fornecedores', FornecedorViewSet, basename='fornecedor')
router.register(r'transportadoras', TransportadoraViewSet, basename='transportadora')
router.register(
    r'condicoes-pagamento',
    CondicaoPagamentoViewSet,
    basename='condicaopagamento',
)
router.register(r'produtos', ProdutoViewSet, basename='produto')
router.register(r'polegadas', PolegadaViewSet, basename='polegada')
router.register(r'ncms', NcmViewSet, basename='ncm')
router.register(r'corridas', CorridaViewSet, basename='corrida')
router.register(r'regras-fiscais', RegraFiscalViewSet, basename='regrafiscal')
router.register(r'propostas', PropostaViewSet, basename='proposta')
router.register(r'pedidos-venda', PedidoVendaViewSet, basename='pedidovenda')
router.register(r'pedidos-compra', PedidoCompraViewSet, basename='pedidocompra')
router.register(r'nf-entradas', NFeEntradaViewSet, basename='nfentrada')
router.register(r'nf-saidas', NFeSaidaViewSet, basename='nfsaida')
router.register(r'cte-entradas', CTeEntradaViewSet, basename='cteentrada')
router.register(r'estoque', EstoqueViewSet, basename='estoque')
router.register(r'contas', ContaViewSet, basename='conta')
router.register(r'lancamentos', LancamentoViewSet, basename='lancamento')
router.register(r'certificados', CertificadoViewSet, basename='certificado')

urlpatterns = [
    path('', include(router.urls)),
    path('apuracao/', ApuracaoView.as_view(), name='apuracao'),
    path('balancete/', BalanceteView.as_view(), name='balancete'),
]
