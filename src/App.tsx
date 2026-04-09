import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import { PrivateRoute } from "./components/PrivateRoute";
import { MainLayout } from "./components/MainLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Empresas from "./pages/Empresas";
import Clientes from "./pages/Clientes";
import Fornecedores from "./pages/Fornecedores";
import Transportadoras from "./pages/Transportadoras";
import Produtos from "./pages/Produtos";
import Corridas from "./pages/Corridas";
import RegrasFiscais from "./pages/RegrasFiscais";
import Propostas from "./pages/Propostas";
import PedidosVenda from "./pages/PedidosVenda";
import PedidosCompra from "./pages/PedidosCompra";
import NFeEntrada from "./pages/NFeEntrada";
import NFeSaida from "./pages/NFeSaida";
import CTeEntrada from "./pages/CTeEntrada";
import Certificados from "./pages/Certificados";
import Estoque from "./pages/Estoque";
import ApuracaoFiscal from "./pages/ApuracaoFiscal";
import Contabil from "./pages/Contabil";

const App = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><MainLayout /></PrivateRoute>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="empresas" element={<Empresas />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="fornecedores" element={<Fornecedores />} />
        <Route path="transportadoras" element={<Transportadoras />} />
        <Route path="produtos" element={<Produtos />} />
        <Route path="corridas" element={<Corridas />} />
        <Route path="regras-fiscais" element={<RegrasFiscais />} />
        <Route path="propostas" element={<Propostas />} />
        <Route path="pedidos-venda" element={<PedidosVenda />} />
        <Route path="pedidos-compra" element={<PedidosCompra />} />
        <Route path="nfe-entrada" element={<NFeEntrada />} />
        <Route path="nfe-saida" element={<NFeSaida />} />
        <Route path="cte-entrada" element={<CTeEntrada />} />
        <Route path="certificados" element={<Certificados />} />
        <Route path="estoque" element={<Estoque />} />
        <Route path="apuracao-fiscal" element={<ApuracaoFiscal />} />
        <Route path="contabil" element={<Contabil />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  </BrowserRouter>
);

export default App;
