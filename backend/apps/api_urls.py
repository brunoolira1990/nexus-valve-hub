from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.apuracao_fiscal.views import ApuracaoView
from apps.cadastros.colaborador_views import ColaboradorViewSet
from apps.cadastros.usuario_views import UsuarioViewSet
from apps.cadastros.views import (
    ClienteViewSet,
    EmpresaViewSet,
    FornecedorViewSet,
    TransportadoraViewSet,
)
from apps.comercial.views import PedidoCompraViewSet, PedidoVendaViewSet, PropostaViewSet
from apps.comercial.vendedor_views import VendedorViewSet
from apps.contabil.views import BalanceteView, ContaViewSet, LancamentoViewSet
from apps.corridas.views import CorridaViewSet
from apps.fiscal.nfe_integracao.views import NFeSefazIntegracaoViewSet
from apps.fiscal.views import (
    AtendimentoEstoqueViewSet,
    CTeEntradaViewSet,
    CTeHistoricoImportadoViewSet,
    EstoqueSaldosConsolidadosViewSet,
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
from apps.regras_fiscais.views import (
    CenarioFiscalEntradaViewSet,
    CenarioFiscalSaidaViewSet,
    RegraFiscalEntradaViewSet,
    RegraFiscalSaidaViewSet,
    RegraFiscalViewSet,
)

router = DefaultRouter()
router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'colaboradores', ColaboradorViewSet, basename='colaborador')
router.register(r'usuarios', UsuarioViewSet, basename='usuario')
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
router.register(r'regras-fiscais-entrada', RegraFiscalEntradaViewSet, basename='regrafiscal-entrada')
router.register(
    r'cenarios-fiscais-entrada',
    CenarioFiscalEntradaViewSet,
    basename='cenario-fiscal-entrada',
)
router.register(r'regras-fiscais-saida', RegraFiscalSaidaViewSet, basename='regrafiscal-saida')
router.register(
    r'cenarios-fiscais-saida',
    CenarioFiscalSaidaViewSet,
    basename='cenario-fiscal-saida',
)
router.register(r'vendedores', VendedorViewSet, basename='vendedor')
router.register(r'propostas', PropostaViewSet, basename='proposta')
router.register(r'pedidos-venda', PedidoVendaViewSet, basename='pedidovenda')
router.register(r'pedidos-compra', PedidoCompraViewSet, basename='pedidocompra')
router.register(r'nf-entradas', NFeEntradaViewSet, basename='nfentrada')
router.register(r'nf-saidas', NFeSaidaViewSet, basename='nfsaida')
router.register(r'nfe-sefaz-status', NFeSefazIntegracaoViewSet, basename='nfe-sefaz-status')
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
router.register(
    r'estoque/saldos-consolidados',
    EstoqueSaldosConsolidadosViewSet,
    basename='estoque-saldos-consolidados',
)
router.register(r'atendimentos-estoque', AtendimentoEstoqueViewSet, basename='atendimento-estoque')
router.register(r'contas', ContaViewSet, basename='conta')
router.register(r'lancamentos', LancamentoViewSet, basename='lancamento')
router.register(r'certificados', CertificadoViewSet, basename='certificado')
router.register(r'certificados-qualidade', CertificadoQualidadeViewSet, basename='certificado-qualidade')
router.register(r'certificados-fornecedor', CertificadoFornecedorEntradaViewSet, basename='certificado-fornecedor')

urlpatterns = [
    # Rotas explícitas: garantem endpoints críticos mesmo com runserver --noreload (Docker).
    # Após alterar apps/api_urls.py ou views, reinicie: docker compose restart backend
    path(
        'pedidos-compra/<int:pk>/pdf/',
        PedidoCompraViewSet.as_view({'get': 'pdf'}),
        name='pedidocompra-pdf',
    ),
    path(
        'cenarios-fiscais-saida/',
        CenarioFiscalSaidaViewSet.as_view({'get': 'list'}),
        name='cenario-fiscal-saida-list-explicit',
    ),
    path(
        'cenarios-fiscais-saida/<int:pk>/',
        CenarioFiscalSaidaViewSet.as_view({'get': 'retrieve'}),
        name='cenario-fiscal-saida-detail-explicit',
    ),
    path(
        'cenarios-fiscais-saida/<int:pk>/escopos/',
        CenarioFiscalSaidaViewSet.as_view({'get': 'escopos', 'post': 'escopos'}),
        name='cenario-fiscal-saida-escopos-explicit',
    ),
    path(
        'cenarios-fiscais-saida/<int:pk>/escopos/<int:escopo_id>/matriz/',
        CenarioFiscalSaidaViewSet.as_view({'get': 'matriz_escopo'}),
        name='cenario-fiscal-saida-matriz-explicit',
    ),
    path('', include(router.urls)),
    path('fiscal/apuracao/', ApuracaoView.as_view(), name='fiscal-apuracao'),
    path('apuracao/', ApuracaoView.as_view(), name='apuracao'),
    path('balancete/', BalanceteView.as_view(), name='balancete'),
]
