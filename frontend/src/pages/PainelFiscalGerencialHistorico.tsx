import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { apiErrorMessage } from '@/services/api/config';
import { clientesService } from '@/services/api/clientes';
import { empresasService } from '@/services/api/empresas';
import { fornecedoresService } from '@/services/api/fornecedores';
import { transportadorasService } from '@/services/api/transportadoras';
import { painelFiscalGerencialHistoricoService, type PainelFiscalGerencialHistoricoResponse } from '@/services/api/painelFiscalGerencialHistorico';
import type { Cliente, Empresa, Fornecedor, Transportadora } from '@/types';

type PeriodoTipo = 'mes' | 'trimestre' | 'intervalo';

const fmtBrl = (n: number) => n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const fmtPct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(2)} %`);

const defaultMes = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
};

const defaultTri = () => {
  const d = new Date();
  return { ano: d.getFullYear(), q: (Math.floor(d.getMonth() / 3) + 1) as 1 | 2 | 3 | 4 };
};

function buildQuery(
  tipo: PeriodoTipo,
  mes: string,
  anoTri: number,
  numTri: 1 | 2 | 3 | 4,
  di: string,
  df: string,
  empresaId: string,
  clienteId: string,
  fornecedorId: string,
  transportadoraId: string,
) {
  const qs = new URLSearchParams();
  if (tipo === 'mes') qs.set('mes', mes);
  else if (tipo === 'trimestre') qs.set('trimestre', `${anoTri}-Q${numTri}`);
  else {
    qs.set('data_inicio', di);
    qs.set('data_fim', df);
  }
  if (empresaId) qs.set('empresa_id', empresaId);
  if (clienteId) qs.set('cliente_id', clienteId);
  if (fornecedorId) qs.set('fornecedor_id', fornecedorId);
  if (transportadoraId) qs.set('transportadora_id', transportadoraId);
  return qs;
}

export default function PainelFiscalGerencialHistorico() {
  const tri = useMemo(() => defaultTri(), []);
  const [periodoTipo, setPeriodoTipo] = useState<PeriodoTipo>('mes');
  const [mes, setMes] = useState(defaultMes);
  const [anoTri, setAnoTri] = useState(tri.ano);
  const [numTri, setNumTri] = useState<1 | 2 | 3 | 4>(tri.q);
  const [di, setDi] = useState(new Date().toISOString().slice(0, 8) + '01');
  const [df, setDf] = useState(new Date().toISOString().slice(0, 10));
  const [empresaId, setEmpresaId] = useState('');
  const [clienteId, setClienteId] = useState('');
  const [fornecedorId, setFornecedorId] = useState('');
  const [transportadoraId, setTransportadoraId] = useState('');

  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [transportadoras, setTransportadoras] = useState<Transportadora[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [painel, setPainel] = useState<PainelFiscalGerencialHistoricoResponse | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [e, c, f, t] = await Promise.all([
          empresasService.getAll(),
          clientesService.getAll(),
          fornecedoresService.getAll(),
          transportadorasService.getAll(),
        ]);
        setEmpresas(e);
        setClientes(c);
        setFornecedores(f);
        setTransportadoras(t);
      } catch (error) {
        setErr(apiErrorMessage(error, { fallback: 'Falha ao carregar filtros.' }));
      }
    })();
  }, []);

  const carregar = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const qs = buildQuery(periodoTipo, mes, anoTri, numTri, di, df, empresaId, clienteId, fornecedorId, transportadoraId);
      setPainel(await painelFiscalGerencialHistoricoService.get(qs));
    } catch (error) {
      setPainel(null);
      setErr(apiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [periodoTipo, mes, anoTri, numTri, di, df, empresaId, clienteId, fornecedorId, transportadoraId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const fat = painel?.bloco_faturamento;
  const comp = painel?.bloco_compras;
  const fre = painel?.bloco_fretes;
  const vis = painel?.visao_comparativa;

  return (
    <div>
      <PageHeader title="Painel fiscal/gerencial consolidado (historico)" />
      <div className="erp-card p-4 mb-6 space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:flex xl:flex-wrap gap-2 items-end">
          <select className="erp-select w-full xl:w-auto" value={periodoTipo} onChange={(e) => setPeriodoTipo(e.target.value as PeriodoTipo)}>
            <option value="mes">Mes</option>
            <option value="trimestre">Trimestre</option>
            <option value="intervalo">Intervalo</option>
          </select>
          {periodoTipo === 'mes' && <input type="month" className="erp-input w-full xl:w-auto" value={mes} onChange={(e) => setMes(e.target.value)} />}
          {periodoTipo === 'trimestre' && (
            <>
              <input type="number" className="erp-input w-full sm:w-24" value={anoTri} onChange={(e) => setAnoTri(Number(e.target.value))} />
              <select className="erp-select w-full xl:w-auto" value={numTri} onChange={(e) => setNumTri(Number(e.target.value) as 1 | 2 | 3 | 4)}>
                <option value={1}>Q1</option><option value={2}>Q2</option><option value={3}>Q3</option><option value={4}>Q4</option>
              </select>
            </>
          )}
          {periodoTipo === 'intervalo' && (
            <>
              <input type="date" className="erp-input w-full xl:w-auto" value={di} onChange={(e) => setDi(e.target.value)} />
              <input type="date" className="erp-input w-full xl:w-auto" value={df} onChange={(e) => setDf(e.target.value)} />
            </>
          )}
          <select className="erp-select w-full xl:w-auto" value={empresaId} onChange={(e) => setEmpresaId(e.target.value)}>
            <option value="">Empresa</option>{empresas.map((v) => <option key={v.id} value={v.id}>{v.razao_social}</option>)}
          </select>
          <select className="erp-select w-full xl:w-auto" value={clienteId} onChange={(e) => setClienteId(e.target.value)}>
            <option value="">Cliente</option>{clientes.map((v) => <option key={v.id} value={v.id}>{v.razao_social}</option>)}
          </select>
          <select className="erp-select w-full xl:w-auto" value={fornecedorId} onChange={(e) => setFornecedorId(e.target.value)}>
            <option value="">Fornecedor</option>{fornecedores.map((v) => <option key={v.id} value={v.id}>{v.razao_social}</option>)}
          </select>
          <select className="erp-select w-full xl:w-auto" value={transportadoraId} onChange={(e) => setTransportadoraId(e.target.value)}>
            <option value="">Transportadora</option>{transportadoras.map((v) => <option key={v.id} value={v.id}>{v.razao_social}</option>)}
          </select>
          <button type="button" className="erp-btn-primary w-full sm:w-auto justify-center" onClick={() => void carregar()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-1 inline ${loading ? 'animate-spin' : ''}`} />Atualizar
          </button>
        </div>
        {err && <p className="text-sm text-destructive">{err}</p>}
      </div>

      {painel && fat && comp && fre && vis && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
            <div className="erp-card p-3"><div className="text-xs">Faturamento</div><div className="font-semibold">{fmtBrl(fat.totais.faturamento_bruto)}</div></div>
            <div className="erp-card p-3"><div className="text-xs">Compras</div><div className="font-semibold">{fmtBrl(comp.totais.valor_total_compras)}</div></div>
            <div className="erp-card p-3"><div className="text-xs">Fretes</div><div className="font-semibold">{fmtBrl(fre.totais.valor_total_fretes)}</div></div>
            <div className="erp-card p-3"><div className="text-xs">Dif. venda x compra</div><div className="font-semibold">{fmtBrl(vis.diferenca_venda_compra)}</div></div>
            <div className="erp-card p-3"><div className="text-xs">Peso frete</div><div className="font-semibold">{fmtPct(vis.peso_frete_sobre_faturamento_pct)}</div></div>
            <div className="erp-card p-3"><div className="text-xs">Peso carga tributaria</div><div className="font-semibold">{fmtPct(vis.peso_carga_tributaria_sobre_faturamento_pct)}</div></div>
          </div>

          <div className="erp-card overflow-x-auto">
            <h3 className="font-medium text-sm p-4 pb-1">Fretes por transportadora</h3>
            <table className="erp-table text-sm" data-mobile-table-mode="cards">
              <thead><tr><th>Transportadora</th><th>Total frete</th></tr></thead>
              <tbody>
                {fre.totais.total_por_transportadora.map((row) => (
                  <tr key={row.transportadora_nome}><td>{row.transportadora_nome}</td><td>{fmtBrl(row.valor_total_frete)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
