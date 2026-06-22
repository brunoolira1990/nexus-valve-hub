from django.urls import include, path
from nexus_erp.dashboard_views import (
    dashboard_comercial,
    dashboard_compras,
    dashboard_estoque,
    dashboard_financeiro,
    dashboard_fiscal,
    dashboard_home,
    dashboard_permissoes,
    dashboard_qualidade,
    dashboard_resumo,
)
from rest_framework.routers import DefaultRouter

from apps.apuracao_fiscal.views import ApuracaoView
from apps.core.app_views import app_contexto, busca_global, minha_conta
from apps.core.minha_conta_views import alterar_senha
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
from apps.financeiro.views import (
    BaixaFinanceiraViewSet,
    CategoriaFinanceiraViewSet,
    CentroCustoViewSet,
    ContaFinanceiraViewSet,
    ContaPagarViewSet,
    ContaReceberViewSet,
    CreditoFinanceiroViewSet,
    financeiro_formas_fixas,
    financeiro_relatorio_categorias,
    financeiro_relatorio_categorias_pdf,
    financeiro_relatorio_clientes,
    financeiro_relatorio_clientes_pdf,
    financeiro_relatorio_contas_pagar,
    financeiro_relatorio_contas_pagar_pdf,
    financeiro_relatorio_contas_receber,
    financeiro_relatorio_contas_receber_pdf,
    financeiro_relatorio_fluxo_previsto,
    financeiro_relatorio_fluxo_previsto_pdf,
    financeiro_relatorio_fornecedores,
    financeiro_relatorio_fornecedores_pdf,
    financeiro_resumo_operacional,
)
from apps.expedicao.views import ExpedicaoViewSet
from apps.corridas.views import CorridaViewSet
from apps.fiscal.nfe_integracao.views import NFeSefazIntegracaoViewSet
from apps.fiscal.central_dfe.views import CentralDfeViewSet
from apps.fiscal.dfe_recebidos.views import DfeRecebidosCapturaView
from apps.fiscal.manifestacao_destinatario.views import ManifestacaoDestinatarioViewSet
from apps.fiscal.views import (
    AlocacaoAtendimentoViewSet,
    AtendimentosOperacionaisViewSet,
    AtendimentoEstoqueViewSet,
    CTeEntradaViewSet,
    CTeHistoricoImportadoViewSet,
    EstoqueSaldosConsolidadosViewSet,
    EstoqueSaldosViewSet,
    EstoqueViewSet,
    NFeEntradaViewSet,
    NFeEntradaHistoricaImportadaViewSet,
    NFeSaidaHistoricaImportadaViewSet,
    NFeNumeracaoConfiguracaoViewSet,
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
from apps.produtos.views_equivalencia import (
    FornecedorComposicaoEquivalenciaViewSet,
    FornecedorProdutoEquivalenciaViewSet,
    ProdutoComposicaoViewSet,
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
router.register(r'produto-composicoes', ProdutoComposicaoViewSet, basename='produto-composicao')
router.register(r'fornecedor-produto-equivalencias', FornecedorProdutoEquivalenciaViewSet, basename='fornecedor-produto-equivalencia')
router.register(
    r'fornecedor-composicao-equivalencias',
    FornecedorComposicaoEquivalenciaViewSet,
    basename='fornecedor-composicao-equivalencia',
)
router.register(r'familias-produto', FamiliaProdutoViewSet, basename='familiaproduto')
router.register(r'familias-produto-polegadas-permitidas', FamiliaProdutoPolegadaPermitidaViewSet, basename='familia-polegada-permitida')
router.register(r'familias-produto-roscas-permitidas', FamiliaProdutoRoscaConexaoPermitidaViewSet, basename='familia-rosca-permitida')
router.register(r'familias-produto-schedules-permitidos', FamiliaProdutoSchedulePermitidoViewSet, basename='familia-schedule-permitido')
router.register(r'roscas-conexao', RoscaConexaoViewSet, basename='roscaconexao')
router.register(r'schedules-espessura', ScheduleEspessuraViewSet, basename='scheduleespessura')
router.register(r'polegadas', PolegadaViewSet, basename='polegada')
router.register(r'ncms', NcmViewSet, basename='ncm')
router.register(r'expedicoes', ExpedicaoViewSet, basename='expedicao')
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
router.register(r'nfe-numeracoes', NFeNumeracaoConfiguracaoViewSet, basename='nfe-numeracao')
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
router.register(r'central-dfe', CentralDfeViewSet, basename='central-dfe')
router.register(
    r'fiscal/manifestacao-destinatario',
    ManifestacaoDestinatarioViewSet,
    basename='manifestacao-destinatario',
)
router.register(r'estoque', EstoqueViewSet, basename='estoque')
router.register(r'estoque/saldos', EstoqueSaldosViewSet, basename='estoque-saldos')
router.register(
    r'estoque/saldos-consolidados',
    EstoqueSaldosConsolidadosViewSet,
    basename='estoque-saldos-consolidados',
)
router.register(r'atendimentos-estoque', AtendimentoEstoqueViewSet, basename='atendimento-estoque')
router.register(
    r'atendimentos-operacionais',
    AtendimentosOperacionaisViewSet,
    basename='atendimento-operacional',
)
router.register(r'alocacoes-atendimento', AlocacaoAtendimentoViewSet, basename='alocacao-atendimento')
router.register(r'contas', ContaViewSet, basename='conta')
router.register(r'lancamentos', LancamentoViewSet, basename='lancamento')
router.register(r'certificados', CertificadoViewSet, basename='certificado')
router.register(r'certificados-qualidade', CertificadoQualidadeViewSet, basename='certificado-qualidade')
router.register(r'certificados-fornecedor', CertificadoFornecedorEntradaViewSet, basename='certificado-fornecedor')
router.register(r'financeiro/contas', ContaFinanceiraViewSet, basename='financeiro-conta')
router.register(r'financeiro/categorias', CategoriaFinanceiraViewSet, basename='financeiro-categoria')
router.register(r'financeiro/centros-custo', CentroCustoViewSet, basename='financeiro-centro-custo')
router.register(r'financeiro/contas-receber', ContaReceberViewSet, basename='financeiro-conta-receber')
router.register(r'financeiro/contas-pagar', ContaPagarViewSet, basename='financeiro-conta-pagar')
router.register(r'financeiro/baixas', BaixaFinanceiraViewSet, basename='financeiro-baixa')
router.register(r'financeiro/creditos', CreditoFinanceiroViewSet, basename='financeiro-credito')

urlpatterns = [
    # Rotas explícitas: garantem endpoints críticos mesmo com runserver --noreload (Docker).
    # Após alterar apps/api_urls.py ou views, reinicie: docker compose restart backend
    path(
        'central-dfe/',
        CentralDfeViewSet.as_view({'get': 'list'}),
        name='central-dfe-list-explicit',
    ),
    path(
        'central-dfe/<int:pk>/armazenar-xml-nfe/',
        CentralDfeViewSet.as_view({'post': 'armazenar_xml_nfe'}),
        name='central-dfe-armazenar-xml-nfe-explicit',
    ),
    path(
        'central-dfe/<int:pk>/armazenar-xml-cte/',
        CentralDfeViewSet.as_view({'post': 'armazenar_xml_cte'}),
        name='central-dfe-armazenar-xml-cte-explicit',
    ),
    path(
        'dfe-recebidos/capturar/',
        DfeRecebidosCapturaView.as_view(),
        name='dfe-recebidos-capturar',
    ),
    path(
        'fiscal/manifestacao-destinatario/',
        ManifestacaoDestinatarioViewSet.as_view({'get': 'list'}),
        name='manifestacao-destinatario-list-explicit',
    ),
    path(
        'fiscal/manifestacao-destinatario/iniciar-por-chave/',
        ManifestacaoDestinatarioViewSet.as_view({'post': 'iniciar_por_chave'}),
        name='manifestacao-destinatario-iniciar-por-chave-explicit',
    ),
    path(
        'fiscal/manifestacao-destinatario/consultar/',
        ManifestacaoDestinatarioViewSet.as_view({'post': 'consultar'}),
        name='manifestacao-destinatario-consultar-explicit',
    ),
    path(
        'fiscal/manifestacao-destinatario/fechamento-preview/',
        ManifestacaoDestinatarioViewSet.as_view({'get': 'fechamento_preview'}),
        name='manifestacao-destinatario-fechamento-explicit',
    ),
    path(
        'fiscal/manifestacao-destinatario/<int:pk>/',
        ManifestacaoDestinatarioViewSet.as_view({'get': 'retrieve'}),
        name='manifestacao-destinatario-detail-explicit',
    ),
    path(
        'fiscal/manifestacao-destinatario/<int:pk>/manifestar/',
        ManifestacaoDestinatarioViewSet.as_view({'post': 'manifestar'}),
        name='manifestacao-destinatario-manifestar-explicit',
    ),
    path(
        'fiscal/manifestacao-destinatario/<int:pk>/baixar-xml/',
        ManifestacaoDestinatarioViewSet.as_view({'post': 'baixar_xml'}),
        name='manifestacao-destinatario-baixar-xml-explicit',
    ),
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
    path('dashboard/permissoes/', dashboard_permissoes, name='dashboard-permissoes'),
    path('dashboard/home/', dashboard_home, name='dashboard-home'),
    path('dashboard/comercial/', dashboard_comercial, name='dashboard-comercial'),
    path('dashboard/fiscal/', dashboard_fiscal, name='dashboard-fiscal'),
    path('dashboard/estoque/', dashboard_estoque, name='dashboard-estoque'),
    path('dashboard/compras/', dashboard_compras, name='dashboard-compras'),
    path('dashboard/qualidade/', dashboard_qualidade, name='dashboard-qualidade'),
    path('dashboard/financeiro/', dashboard_financeiro, name='dashboard-financeiro'),
    path('financeiro/resumo/', financeiro_resumo_operacional, name='financeiro-resumo'),
    path('financeiro/formas-fixas/', financeiro_formas_fixas, name='financeiro-formas-fixas'),
    path(
        'financeiro/relatorios/contas-receber/',
        financeiro_relatorio_contas_receber,
        name='financeiro-relatorio-cr',
    ),
    path(
        'financeiro/relatorios/contas-pagar/',
        financeiro_relatorio_contas_pagar,
        name='financeiro-relatorio-cp',
    ),
    path(
        'financeiro/relatorios/fluxo-previsto/',
        financeiro_relatorio_fluxo_previsto,
        name='financeiro-relatorio-fluxo',
    ),
    path(
        'financeiro/relatorios/categorias/',
        financeiro_relatorio_categorias,
        name='financeiro-relatorio-categorias',
    ),
    path(
        'financeiro/relatorios/clientes/',
        financeiro_relatorio_clientes,
        name='financeiro-relatorio-clientes',
    ),
    path(
        'financeiro/relatorios/fornecedores/',
        financeiro_relatorio_fornecedores,
        name='financeiro-relatorio-fornecedores',
    ),
    path(
        'financeiro/relatorios/contas-receber/pdf/',
        financeiro_relatorio_contas_receber_pdf,
        name='financeiro-relatorio-cr-pdf',
    ),
    path(
        'financeiro/relatorios/contas-pagar/pdf/',
        financeiro_relatorio_contas_pagar_pdf,
        name='financeiro-relatorio-cp-pdf',
    ),
    path(
        'financeiro/relatorios/fluxo-previsto/pdf/',
        financeiro_relatorio_fluxo_previsto_pdf,
        name='financeiro-relatorio-fluxo-pdf',
    ),
    path(
        'financeiro/relatorios/categorias/pdf/',
        financeiro_relatorio_categorias_pdf,
        name='financeiro-relatorio-categorias-pdf',
    ),
    path(
        'financeiro/relatorios/clientes/pdf/',
        financeiro_relatorio_clientes_pdf,
        name='financeiro-relatorio-clientes-pdf',
    ),
    path(
        'financeiro/relatorios/fornecedores/pdf/',
        financeiro_relatorio_fornecedores_pdf,
        name='financeiro-relatorio-fornecedores-pdf',
    ),
    path('app/contexto/', app_contexto, name='app-contexto'),
    path('busca-global/', busca_global, name='busca-global'),
    path('minha-conta/', minha_conta, name='minha-conta'),
    path('minha-conta/alterar-senha/', alterar_senha, name='minha-conta-alterar-senha'),
    path('dashboard/resumo/', dashboard_resumo, name='dashboard-resumo'),
    path('fiscal/apuracao/', ApuracaoView.as_view(), name='fiscal-apuracao'),
    path('apuracao/', ApuracaoView.as_view(), name='apuracao'),
    path('balancete/', BalanceteView.as_view(), name='balancete'),
]
