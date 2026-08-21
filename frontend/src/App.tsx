import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { PrivateRoute } from "./components/PrivateRoute";
import { MainLayout } from "./components/MainLayout";
import Login from "./pages/Login";
import DashboardHome from "./pages/dashboard/DashboardHome";
import DashboardComercial from "./pages/dashboard/DashboardComercial";
import DashboardFiscal from "./pages/dashboard/DashboardFiscal";
import DashboardEstoque from "./pages/dashboard/DashboardEstoque";
import DashboardExpedicao from "./pages/dashboard/DashboardExpedicao";
import DashboardCompras from "./pages/dashboard/DashboardCompras";
import DashboardQualidade from "./pages/dashboard/DashboardQualidade";
import DashboardFinanceiro from "./pages/dashboard/DashboardFinanceiro";
import ModuloEmBreve from "./pages/modulos/ModuloEmBreve";
import CRM from "./pages/crm/CRM";
import CRMLeads from "./pages/crm/CRMLeads";
import CRMOportunidades from "./pages/crm/CRMOportunidades";
import CRMAtividades from "./pages/crm/CRMAtividades";
import Notificacoes from "./pages/Notificacoes";
import ContadorExportarXmls from "./pages/contador/ContadorExportarXmls";
import Empresas from "./pages/Empresas";
import ClienteList from "./pages/Clientes/ClienteList";
import ClienteFormPage from "./pages/Clientes/ClienteFormPage";
import FornecedorList from "./pages/Fornecedores/FornecedorList";
import FornecedorFormPage from "./pages/Fornecedores/FornecedorFormPage";
import TransportadoraList from "./pages/Transportadoras/TransportadoraList";
import TransportadoraFormPage from "./pages/Transportadoras/TransportadoraFormPage";
import Colaboradores from "./pages/Colaboradores";
import MinhaConta from "./pages/MinhaConta";
import MinhaContaAlterarSenha from "./pages/MinhaContaAlterarSenha";
import Produtos from "./pages/Produtos";
import Corridas from "./pages/Corridas";
import RegrasFiscais from "./pages/RegrasFiscais";
import Propostas from "./pages/Propostas";
import PedidosVenda from "./pages/PedidosVenda";
import PedidosCompra from "./pages/PedidosCompra";
import NFeEntrada from "./pages/NFeEntrada";
import NFeSaida from "./pages/NFeSaida";
import NFeSefazIntegracao from "./pages/NFeSefazIntegracao";
import CentralDfe from "./pages/CentralDfe";
import ManifestacaoDestinatario from "./pages/ManifestacaoDestinatario";
import NFeHistoricaImportada from "./pages/NFeHistoricaImportada";
import NFeHistoricaEntradaImportada from "./pages/NFeHistoricaEntradaImportada";
import NFeEntradaConferenciaPage from "./pages/NFeEntradaConferencia";
import PainelFiscalGerencialHistorico from "./pages/PainelFiscalGerencialHistorico";
import CTeEntrada from "./pages/CTeEntrada";
import CTeHistoricoImportado from "./pages/CTeHistoricoImportado";
import Certificados from "./pages/Certificados";
import CertificadosFornecedor from "./pages/CertificadosFornecedor";
import Estoque from './pages/Estoque';
import KardexEstoque from './pages/KardexEstoque';
import AtendimentosEstoque from "./pages/AtendimentosEstoque";
import Expedicao from "./pages/Expedicao";
import ApuracaoFiscal from "./pages/ApuracaoFiscal";
import Contabil from "./pages/Contabil";
import FinanceiroVisaoGeral from "./pages/financeiro/FinanceiroVisaoGeral";
import ContasReceber from "./pages/financeiro/ContasReceber";
import ContasPagar from "./pages/financeiro/ContasPagar";
import FinanceiroCadastros from "./pages/financeiro/FinanceiroCadastros";
import Creditos from "./pages/financeiro/Creditos";
import AnalisesFinanceirasPage from "./pages/financeiro/AnalisesFinanceirasPage";
import FinanceiroRelatoriosHub from "./pages/financeiro/relatorios/FinanceiroRelatoriosHub";
import RelatorioContasReceberPage from "./pages/financeiro/relatorios/RelatorioContasReceberPage";
import RelatorioContasPagarPage from "./pages/financeiro/relatorios/RelatorioContasPagarPage";
import RelatorioFluxoPrevistoPage from "./pages/financeiro/relatorios/RelatorioFluxoPrevistoPage";
import RelatorioCategoriasPage from "./pages/financeiro/relatorios/RelatorioCategoriasPage";
import RelatorioClientesPage from "./pages/financeiro/relatorios/RelatorioClientesPage";
import RelatorioFornecedoresPage from "./pages/financeiro/relatorios/RelatorioFornecedoresPage";

const App = () => (
  <BrowserRouter>
    <Toaster richColors closeButton position="top-right" />
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><MainLayout /></PrivateRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardHome />} />
        <Route path="dashboard/comercial" element={<DashboardComercial />} />
        <Route path="dashboard/fiscal" element={<DashboardFiscal />} />
        <Route path="dashboard/estoque" element={<DashboardEstoque />} />
        <Route path="dashboard/expedicao" element={<DashboardExpedicao />} />
        <Route path="dashboard/compras" element={<DashboardCompras />} />
        <Route path="dashboard/qualidade" element={<DashboardQualidade />} />
        <Route path="dashboard/financeiro" element={<DashboardFinanceiro />} />
        <Route path="modulos/:modulo" element={<ModuloEmBreve />} />
        <Route path="crm" element={<CRM />} />
        <Route path="crm/leads" element={<CRMLeads />} />
        <Route path="crm/oportunidades" element={<CRMOportunidades />} />
        <Route path="crm/atividades" element={<CRMAtividades />} />
        <Route path="notificacoes" element={<Notificacoes />} />
        <Route path="contador/exportar-xmls" element={<ContadorExportarXmls />} />
        <Route path="contador/sped" element={<ModuloEmBreve moduloKey="sped" />} />
        <Route path="empresas" element={<Empresas />} />
        <Route path="clientes" element={<ClienteList />} />
        <Route path="clientes/novo" element={<ClienteFormPage />} />
        <Route path="clientes/:id/edit" element={<ClienteFormPage />} />
        <Route path="fornecedores" element={<FornecedorList />} />
        <Route path="fornecedores/novo" element={<FornecedorFormPage />} />
        <Route path="fornecedores/:id/edit" element={<FornecedorFormPage />} />
        <Route path="transportadoras" element={<TransportadoraList />} />
        <Route path="transportadoras/novo" element={<TransportadoraFormPage />} />
        <Route path="transportadoras/:id/edit" element={<TransportadoraFormPage />} />
        <Route path="colaboradores" element={<Colaboradores />} />
        <Route path="minha-conta" element={<MinhaConta />} />
        <Route path="minha-conta/alterar-senha" element={<MinhaContaAlterarSenha />} />
        <Route path="produtos" element={<Produtos />} />
        <Route path="corridas" element={<Corridas />} />
        <Route path="regras-fiscais" element={<RegrasFiscais />} />
        <Route path="propostas" element={<Propostas />} />
        <Route path="pedidos-venda" element={<PedidosVenda />} />
        <Route path="pedidos-compra" element={<PedidosCompra />} />
        <Route path="nfe-entrada" element={<NFeEntrada />} />
        <Route path="nfe-saida" element={<NFeSaida />} />
        <Route path="nfe-sefaz" element={<NFeSefazIntegracao />} />
        <Route path="nfe-historica-importada" element={<NFeHistoricaImportada />} />
        <Route path="central-dfe" element={<CentralDfe />} />
        <Route path="manifestacao-destinatario" element={<ManifestacaoDestinatario />} />
        <Route path="nfe-entrada-historica-importada" element={<NFeHistoricaEntradaImportada />} />
        <Route path="nfe-entrada/:id/conferencia" element={<NFeEntradaConferenciaPage />} />
        <Route path="visao-gerencial-nfe-historica" element={<PainelFiscalGerencialHistorico />} />
        <Route path="cte-entrada" element={<CTeEntrada />} />
        <Route path="cte-historico-importado" element={<CTeHistoricoImportado />} />
        <Route path="certificados" element={<Certificados />} />
        <Route path="certificados-fornecedor" element={<CertificadosFornecedor />} />
        <Route path="estoque" element={<Estoque />} />
        <Route path="estoque/kardex" element={<KardexEstoque />} />
        <Route path="atendimentos-estoque" element={<AtendimentosEstoque />} />
        <Route path="expedicao" element={<Expedicao />} />
        <Route path="apuracao-fiscal" element={<ApuracaoFiscal />} />
        <Route path="contabil" element={<Contabil />} />
        <Route path="financeiro" element={<FinanceiroVisaoGeral />} />
        <Route path="financeiro/contas-receber" element={<ContasReceber />} />
        <Route path="financeiro/contas-pagar" element={<ContasPagar />} />
        <Route path="financeiro/cadastros" element={<FinanceiroCadastros />} />
        <Route path="financeiro/creditos" element={<Creditos />} />
        <Route path="financeiro/analises" element={<AnalisesFinanceirasPage />} />
        <Route path="financeiro/relatorios" element={<FinanceiroRelatoriosHub />} />
        <Route path="financeiro/relatorios/contas-receber" element={<RelatorioContasReceberPage />} />
        <Route path="financeiro/relatorios/contas-pagar" element={<RelatorioContasPagarPage />} />
        <Route path="financeiro/relatorios/fluxo-previsto" element={<RelatorioFluxoPrevistoPage />} />
        <Route path="financeiro/relatorios/categorias" element={<RelatorioCategoriasPage />} />
        <Route path="financeiro/relatorios/clientes" element={<RelatorioClientesPage />} />
        <Route path="financeiro/relatorios/fornecedores" element={<RelatorioFornecedoresPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  </BrowserRouter>
);

export default App;
