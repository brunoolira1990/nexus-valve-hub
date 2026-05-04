from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.apuracao_fiscal.views import ApuracaoView
from apps.cadastros.views import (
    ClienteViewSet,
    EmpresaViewSet,
    FornecedorViewSet,
    TransportadoraViewSet,
)
from apps.comercial.views import PedidoCompraViewSet, PedidoVendaViewSet, PropostaViewSet
from apps.contabil.views import BalanceteView, ContaViewSet, LancamentoViewSet
from apps.corridas.views import CorridaViewSet
from apps.fiscal.views import (
    CTeEntradaViewSet,
    CTeHistoricoImportadoViewSet,
    EstoqueSaldosViewSet,
    EstoqueViewSet,
    NFeEntradaViewSet,
    NFeEntradaHistoricaImportadaViewSet,
    NFeSaidaHistoricaImportadaViewSet,
    NFeSaidaViewSet,
    PainelFiscalGerencialHistoricoViewSet,
)
from apps.produtos.views import (
    FamiliaProdutoViewSet,
    FamiliaProdutoPolegadaPermitidaViewSet,
    FamiliaProdutoRoscaConexaoPermitidaViewSet,
    FamiliaProdutoSchedulePermitidoViewSet,
    NcmViewSet,
    PolegadaViewSet,
    ProdutoViewSet,
    RoscaConexaoViewSet,
    ScheduleEspessuraViewSet,
)
from apps.qualidade.views import (
    CertificadoFornecedorEntradaViewSet,
    CertificadoQualidadeViewSet,
    CertificadoViewSet,
)
from apps.regras_fiscais.views import RegraFiscalViewSet

router = DefaultRouter()
router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'fornecedores', FornecedorViewSet, basename='fornecedor')
router.register(r'transportadoras', TransportadoraViewSet, basename='transportadora')
router.register(r'produtos', ProdutoViewSet, basename='produto')
router.register(r'familias-produto', FamiliaProdutoViewSet, basename='familiaproduto')
router.register(r'familias-produto-polegadas-permitidas', FamiliaProdutoPolegadaPermitidaViewSet, basename='familia-polegada-permitida')
router.register(r'familias-produto-roscas-permitidas', FamiliaProdutoRoscaConexaoPermitidaViewSet, basename='familia-rosca-permitida')
router.register(r'familias-produto-schedules-permitidos', FamiliaProdutoSchedulePermitidoViewSet, basename='familia-schedule-permitido')
router.register(r'roscas-conexao', RoscaConexaoViewSet, basename='roscaconexao')
router.register(r'schedules-espessura', ScheduleEspessuraViewSet, basename='scheduleespessura')
router.register(r'polegadas', PolegadaViewSet, basename='polegada')
router.register(r'ncms', NcmViewSet, basename='ncm')
router.register(r'corridas', CorridaViewSet, basename='corrida')
router.register(r'regras-fiscais', RegraFiscalViewSet, basename='regrafiscal')
router.register(r'propostas', PropostaViewSet, basename='proposta')
router.register(r'pedidos-venda', PedidoVendaViewSet, basename='pedidovenda')
router.register(r'pedidos-compra', PedidoCompraViewSet, basename='pedidocompra')
router.register(r'nf-entradas', NFeEntradaViewSet, basename='nfentrada')
router.register(r'nf-saidas', NFeSaidaViewSet, basename='nfsaida')
router.register(
    r'nf-saidas-historicas-importadas',
    NFeSaidaHistoricaImportadaViewSet,
    basename='nf-saida-hist-importada',
)
router.register(
    r'nf-entradas-historicas-importadas',
    NFeEntradaHistoricaImportadaViewSet,
    basename='nf-entrada-hist-importada',
)
router.register(r'cte-entradas', CTeEntradaViewSet, basename='cteentrada')
router.register(r'cte-historicos-importados', CTeHistoricoImportadoViewSet, basename='cte-hist-importado')
router.register(r'painel-fiscal-gerencial-historico', PainelFiscalGerencialHistoricoViewSet, basename='painel-fiscal-gerencial')
router.register(r'estoque', EstoqueViewSet, basename='estoque')
router.register(r'estoque/saldos', EstoqueSaldosViewSet, basename='estoque-saldos')
router.register(r'contas', ContaViewSet, basename='conta')
router.register(r'lancamentos', LancamentoViewSet, basename='lancamento')
router.register(r'certificados', CertificadoViewSet, basename='certificado')
router.register(r'certificados-qualidade', CertificadoQualidadeViewSet, basename='certificado-qualidade')
router.register(r'certificados-fornecedor', CertificadoFornecedorEntradaViewSet, basename='certificado-fornecedor')

urlpatterns = [
    path('', include(router.urls)),
    path('apuracao/', ApuracaoView.as_view(), name='apuracao'),
    path('balancete/', BalanceteView.as_view(), name='balancete'),
]
