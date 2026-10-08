import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, FileCheck, FileUp, Info, RefreshCw, Printer } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';
import { CTeHistoricoDetalheModal } from '@/components/fiscal/CTeHistoricoDetalheModal';
import { PageHeader } from '@/components/PageHeader';
import { apiErrorMessage } from '@/services/api/config';
import { empresasService } from '@/services/api/empresas';
import { transportadorasService } from '@/services/api/transportadoras';
import type { Empresa, Transportadora } from '@/types';
import {
  cteHistoricoImportadoService,
  type CTeHistImportResultado,
  type CTeHistoricoList,
  type CTeResumoGerencial,
  type CTeSerieGerencial,
  type CTeTransportadoraGerencial,
} from '@/services/api/cteHistoricoImportado';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NexusCard } from '@/components/nexus/NexusCard';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import { openBlobInNewTab } from '@/lib/downloadBlobFile';
import {formatMoneyBRL} from '@/lib/numberFields';

type PeriodoTipo = 'mes' | 'trimestre' | 'intervalo';

function defaultMes(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function defaultTrimestre(): { ano: number; q: 1 | 2 | 3 | 4 } {
  const d = new Date();
  const q = (Math.floor(d.getMonth() / 3) + 1) as 1 | 2 | 3 | 4;
  return { ano: d.getFullYear(), q };
}

function buildQuery(
  tipo: PeriodoTipo,
  mes: string,
  anoTri: number,
  numTri: 1 | 2 | 3 | 4,
  di: string,
  df: string,
  transportadoraId: string,
  empresaTomadoraId: string,
  incluirCancelados: boolean,
  modal: string,
  tipoServico: string,
): URLSearchParams {
  const qs = new URLSearchParams();
  if (tipo === 'mes') qs.set('mes', mes);
  else if (tipo === 'trimestre') qs.set('trimestre', `${anoTri}-Q${numTri}`);
  else {
    qs.set('data_inicio', di);
    qs.set('data_fim', df);
  }
  if (transportadoraId) qs.set('transportadora_id', transportadoraId);
  if (empresaTomadoraId) qs.set('empresa_tomadora_id', empresaTomadoraId);
  if (incluirCancelados) qs.set('incluir_cancelados', 'true');
  if (modal) qs.set('modal', modal);
  if (tipoServico) qs.set('tipo_servico', tipoServico);
  return qs;
}

const toNum = (v: unknown): number => {
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
};

const fmtMoney = (v: unknown): string => formatMoneyBRL(v);

function statusCteHistorico(statusVisual: string): string {
  const s = (statusVisual || 'autorizado').toLowerCase();
  if (s.includes('cancel')) return 'cancelado';
  if (s.includes('pend')) return 'pendente';
  if (s.includes('erro')) return 'erro_processamento';
  if (s.includes('import')) return 'importado';
  return 'processado';
}

function labelAcaoConferencia(status?: string): string {
  const s = status || 'IMPORTADO';
  if (s === 'CONFERIDO') return 'Revisar conferência';
  if (s === 'DIVERGENTE') return 'Revisar divergência';
  return 'Conferir';
}

function mostraAcaoConferir(status?: string): boolean {
  const s = status || 'IMPORTADO';
  return ['IMPORTADO', 'PROCESSADO', 'PREPARADO', 'CONFERIDO', 'DIVERGENTE'].includes(s);
}

const CTeHistoricoImportado = () => {
  const [busy, setBusy] = useState(false);
  const [ultimoResultado, setUltimoResultado] = useState<CTeHistImportResultado | null>(null);
  const [erroUpload, setErroUpload] = useState<string | null>(null);

  const [loadingHistorico, setLoadingHistorico] = useState(false);
  const [erroHistorico, setErroHistorico] = useState<string | null>(null);

  const initTri = useMemo(() => defaultTrimestre(), []);
  const [periodoTipo, setPeriodoTipo] = useState<PeriodoTipo>('mes');
  const [mes, setMes] = useState(defaultMes);
  const [anoTri, setAnoTri] = useState(initTri.ano);
  const [numTri, setNumTri] = useState<1 | 2 | 3 | 4>(initTri.q);
  const [di, setDi] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
  });
  const [df, setDf] = useState(() => new Date().toISOString().slice(0, 10));

  const [transportadoras, setTransportadoras] = useState<Transportadora[]>([]);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [transportadoraId, setTransportadoraId] = useState('');
  const [empresaTomadoraId, setEmpresaTomadoraId] = useState('');
  const [incluirCancelados, setIncluirCancelados] = useState(false);
  const [modalFiltro, setModalFiltro] = useState('');
  const [tipoServicoFiltro, setTipoServicoFiltro] = useState('');
  const [serieTipo, setSerieTipo] = useState<'mensal' | 'trimestral'>('mensal');

  const periodFilters = useMemo(() => {
    const qs = buildQuery(
      periodoTipo,
      mes,
      anoTri,
      numTri,
      di,
      df,
      transportadoraId,
      empresaTomadoraId,
      incluirCancelados,
      modalFiltro,
      tipoServicoFiltro,
    );
    const out: Record<string, string> = {};
    qs.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }, [
    periodoTipo,
    mes,
    anoTri,
    numTri,
    di,
    df,
    transportadoraId,
    empresaTomadoraId,
    incluirCancelados,
    modalFiltro,
    tipoServicoFiltro,
  ]);

  const {
    items,
    count,
    page,
    pageSize,
    totalPages,
    search,
    setSearch,
    setPage,
    setPageSize,
    setFilters,
    loading: loadingList,
    error: loadError,
    reload: reloadList,
  } = usePaginatedList<CTeHistoricoList>({
    fetchPage: cteHistoricoImportadoService.listPaginated,
    initialFilters: periodFilters,
  });

  useEffect(() => {
    setFilters(periodFilters);
  }, [periodFilters, setFilters]);

  const [resumoGerencial, setResumoGerencial] = useState<CTeResumoGerencial | null>(null);
  const [transportadorasGerencial, setTransportadorasGerencial] = useState<CTeTransportadoraGerencial[]>([]);
  const [serieGerencial, setSerieGerencial] = useState<CTeSerieGerencial[]>([]);

  const [detalheId, setDetalheId] = useState<number | null>(null);
  const [detalheRow, setDetalheRow] = useState<CTeHistoricoList | null>(null);
  const [modalDetalhe, setModalDetalhe] = useState(false);
  const [abaInicialConferencia, setAbaInicialConferencia] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const raw = (searchParams.get('id') || '').trim();
    if (!raw) return;
    const id = Number(raw);
    if (!Number.isFinite(id) || id <= 0) return;
    setDetalheId(id);
    setDetalheRow(null);
    setAbaInicialConferencia(false);
    setModalDetalhe(true);
    const next = new URLSearchParams(searchParams);
    next.delete('id');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    void (async () => {
      try {
        const [t, e] = await Promise.all([transportadorasService.getAll(), empresasService.getAll()]);
        setTransportadoras(t);
        setEmpresas(e);
      } catch (e) {
        setErroHistorico(apiErrorMessage(e, { fallback: 'Não foi possível carregar cadastros para os filtros.' }));
      }
    })();
  }, []);

  const loadGerencial = useCallback(async () => {
    setErroHistorico(null);
    setLoadingHistorico(true);
    try {
      const qs = buildQuery(
        periodoTipo,
        mes,
        anoTri,
        numTri,
        di,
        df,
        transportadoraId,
        empresaTomadoraId,
        incluirCancelados,
        modalFiltro,
        tipoServicoFiltro,
      );
      const [resumo, porTransportadora, serieMensal, serieTrimestral] = await Promise.all([
        cteHistoricoImportadoService.resumoGerencial(qs),
        cteHistoricoImportadoService.transportadorasGerencial(qs),
        cteHistoricoImportadoService.serieMensalGerencial(qs),
        cteHistoricoImportadoService.serieTrimestralGerencial(qs),
      ]);
      setResumoGerencial(resumo);
      setTransportadorasGerencial(porTransportadora.transportadoras);
      setSerieGerencial(serieTipo === 'mensal' ? serieMensal.meses : serieTrimestral.trimestres);
    } catch (e) {
      setErroHistorico(apiErrorMessage(e));
      setResumoGerencial(null);
      setTransportadorasGerencial([]);
      setSerieGerencial([]);
    } finally {
      setLoadingHistorico(false);
    }
  }, [periodoTipo, mes, anoTri, numTri, di, df, transportadoraId, empresaTomadoraId, incluirCancelados, modalFiltro, tipoServicoFiltro, serieTipo]);

  useEffect(() => {
    void loadGerencial();
  }, [loadGerencial]);

  const refreshHistorico = useCallback(() => {
    void reloadList();
    void loadGerencial();
  }, [reloadList, loadGerencial]);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setErroUpload(null);
    setBusy(true);
    try {
      const res = await cteHistoricoImportadoService.importarXmls(Array.from(files));
      setUltimoResultado(res);
      await refreshHistorico();
    } catch (e) {
      setErroUpload(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const abrirDetalhe = (row: CTeHistoricoList, irConferencia = false) => {
    setDetalheId(row.id);
    setDetalheRow(row);
    setAbaInicialConferencia(irConferencia);
    setModalDetalhe(true);
  };

  const imprimirDacte = async (row: CTeHistoricoList) => {
    try {
      const blob = await cteHistoricoImportadoService.dacteBlob(row.id);
      openBlobInNewTab(blob, `DACTE_CTe_${row.id}.pdf`);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível gerar o DACTE.' }));
    }
  };

  const arquivosProcessados = useMemo(() => {
    if (!ultimoResultado) return [];
    const out = new Set<string>();
    ultimoResultado.importados.forEach((x) => out.add(x.arquivo));
    ultimoResultado.duplicados.forEach((x) => out.add(x.arquivo));
    ultimoResultado.erros.forEach((x) => out.add(x.arquivo));
    return Array.from(out).sort((a, b) => a.localeCompare(b));
  }, [ultimoResultado]);

  return (
    <div>
      <PageHeader
        title="Base de CT-e Importada"
        description="XMLs de transporte usados para apuração, análise logística, frete médio e precificação. Não geram contas a pagar ou vínculo operacional automaticamente."
        searchValue={search}
        onSearch={setSearch}
      />

      <p className="text-sm text-muted-foreground mb-4">
        <Link to="/cte-entrada" className="text-primary underline-offset-4 hover:underline">
          Ir para CT-e de entrada (operacional)
        </Link>
      </p>

      <NexusCard className="p-6 mb-6 border-dashed border-2 border-border">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="flex-1">
            <h2 className="font-semibold text-foreground flex items-center gap-2">
              <FileUp className="h-5 w-5" />
              Importar XMLs de CT-e
            </h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              Alimenta apuração, custo logístico, frete médio e precificação. Sem efeito operacional automático (contas a pagar, expedição, vínculo obrigatório com NF-e).
            </p>
          </div>
          <label className="erp-btn-primary cursor-pointer shrink-0">
            <input
              type="file"
              accept=".xml,application/xml,text/xml"
              multiple
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                void onFiles(e.target.files);
                e.target.value = '';
              }}
            />
            {busy ? 'Importando…' : 'Selecionar XMLs'}
          </label>
        </div>
        {erroUpload && (
          <div className="mt-4 flex items-start gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{erroUpload}</span>
          </div>
        )}
      </NexusCard>

      {ultimoResultado && (
        <div className="erp-card p-6 mb-8">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div>
              <h2 className="text-base font-semibold text-foreground">Resultado desta importação</h2>
              <p className="text-sm text-muted-foreground">
                Refere-se somente ao último lote enviado ({ultimoResultado.resumo.total_arquivos} arquivo(s) processado(s)).
              </p>
            </div>
            <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => setUltimoResultado(null)}>
              Limpar resultado
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="erp-card p-4 border-l-4 border-l-success">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">Importados</div>
              <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.importados}</div>
              {ultimoResultado.importados.length > 0 && (
                <ul className="mt-2 text-xs text-muted-foreground space-y-1 max-h-28 overflow-y-auto">
                  {ultimoResultado.importados.map((i) => (
                    <li key={i.chave_acesso}>
                      <FileCheck className="inline h-3 w-3 mr-1 text-success" />
                      {i.arquivo} — CT-e {i.numero}/{i.serie}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="erp-card p-4 border-l-4 border-l-muted-foreground">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">Duplicados</div>
              <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.duplicados}</div>
            </div>
            <div className="erp-card p-4 border-l-4 border-l-destructive">
              <div className="text-xs text-muted-foreground uppercase tracking-wide">Erros de leitura</div>
              <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.erros}</div>
            </div>
          </div>

          {arquivosProcessados.length > 0 && (
            <div className="mt-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Arquivos processados</div>
              <div className="erp-card p-3 bg-muted/30">
                <ul className="text-xs text-muted-foreground grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1 max-h-40 overflow-y-auto">
                  {arquivosProcessados.map((a) => (
                    <li key={a} className="truncate" title={a}>
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      <NexusCard className="p-4 mb-4">
        <p className="text-sm text-muted-foreground flex gap-2 items-start">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            <strong className="text-foreground">Histórico de CT-e importados</strong>: a grade abaixo é acumulada e reflete todos os CT-es já importados no período filtrado.
          </span>
        </p>

        <div className="flex flex-col sm:flex-row sm:flex-wrap gap-3 items-stretch sm:items-end mt-4">
          <div>
            <label className="erp-label">Período</label>
            <select className="erp-select mt-1 w-full sm:w-auto min-w-0 sm:min-w-[160px]" value={periodoTipo} onChange={(e) => setPeriodoTipo(e.target.value as PeriodoTipo)}>
              <option value="mes">Mês</option>
              <option value="trimestre">Trimestre</option>
              <option value="intervalo">Data inicial / final</option>
            </select>
          </div>
          {periodoTipo === 'mes' && (
            <div>
              <label className="erp-label">Mês</label>
              <input type="month" className="erp-input mt-1 w-full sm:w-auto" value={mes} onChange={(e) => setMes(e.target.value)} />
            </div>
          )}
          {periodoTipo === 'trimestre' && (
            <>
              <div>
                <label className="erp-label">Ano</label>
                <input type="number" className="erp-input mt-1 w-full sm:w-28" value={anoTri} onChange={(e) => setAnoTri(Number(e.target.value))} min={2000} max={2100} />
              </div>
              <div>
                <label className="erp-label">Trimestre</label>
                <select className="erp-select mt-1 w-full sm:w-auto" value={numTri} onChange={(e) => setNumTri(Number(e.target.value) as 1 | 2 | 3 | 4)}>
                  <option value={1}>Q1</option>
                  <option value={2}>Q2</option>
                  <option value={3}>Q3</option>
                  <option value={4}>Q4</option>
                </select>
              </div>
            </>
          )}
          {periodoTipo === 'intervalo' && (
            <>
              <div>
                <label className="erp-label">Início</label>
                <input type="date" className="erp-input mt-1 w-full sm:w-auto" value={di} onChange={(e) => setDi(e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Fim</label>
                <input type="date" className="erp-input mt-1 w-full sm:w-auto" value={df} onChange={(e) => setDf(e.target.value)} />
              </div>
            </>
          )}
          <div>
            <label className="erp-label">Transportadora</label>
            <select className="erp-select mt-1 w-full sm:w-auto min-w-0 sm:min-w-[220px]" value={transportadoraId} onChange={(e) => setTransportadoraId(e.target.value)}>
              <option value="">Todas</option>
              {transportadoras.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.razao_social}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Empresa tomadora</label>
            <select className="erp-select mt-1 w-full sm:w-auto min-w-0 sm:min-w-[220px]" value={empresaTomadoraId} onChange={(e) => setEmpresaTomadoraId(e.target.value)}>
              <option value="">Todas</option>
              {empresas.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.razao_social}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Modal</label>
            <input className="erp-input mt-1 w-full sm:w-auto min-w-0 sm:min-w-[100px]" placeholder="Ex.: 01" value={modalFiltro} onChange={(e) => setModalFiltro(e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Tipo serviço</label>
            <input className="erp-input mt-1 w-full sm:w-auto min-w-0 sm:min-w-[100px]" placeholder="Ex.: 0" value={tipoServicoFiltro} onChange={(e) => setTipoServicoFiltro(e.target.value)} />
          </div>
          <label className="inline-flex items-center gap-2 mt-2 sm:mt-5 text-sm text-muted-foreground">
            <input type="checkbox" checked={incluirCancelados} onChange={(e) => setIncluirCancelados(e.target.checked)} />
            Incluir cancelados
          </label>
          <button type="button" className="erp-btn-primary w-full sm:w-auto mt-1 sm:mt-5" onClick={() => void refreshHistorico()} disabled={loadingHistorico || loadingList}>
            <RefreshCw className={`h-4 w-4 mr-1 inline ${loadingHistorico ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
        </div>
        {erroHistorico && <p className="text-sm text-destructive mt-3">{erroHistorico}</p>}
      </NexusCard>

      {resumoGerencial && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Fretes no período</div><div className="font-semibold">{fmtMoney(resumoGerencial.totais.valor_total_fretes)}</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">CT-es válidos</div><div className="font-semibold">{resumoGerencial.totais.quantidade_ctes}</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Frete médio</div><div className="font-semibold">{fmtMoney(resumoGerencial.totais.frete_medio)}</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Peso sobre faturamento</div><div className="font-semibold">{(resumoGerencial.indicadores_gerenciais.peso_frete_sobre_faturamento_pct ?? 0).toFixed(2)}%</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Peso sobre compras</div><div className="font-semibold">{(resumoGerencial.indicadores_gerenciais.peso_frete_sobre_compras_pct ?? 0).toFixed(2)}%</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Faturamento base para comparação</div><div className="font-semibold">{fmtMoney(resumoGerencial.base_comparativa.faturamento)}</div><p className="text-[10px] text-muted-foreground mt-0.5">Peso do frete sobre faturamento (base importada).</p></div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="erp-card overflow-x-auto">
          <h3 className="font-medium text-sm p-4 pb-1">Fretes por transportadora</h3>
          <table className="erp-table text-sm" data-mobile-table-mode="cards">
            <thead><tr><th>Transportadora</th><th>CT-es</th><th>Total</th><th>Médio</th><th>Part. %</th></tr></thead>
            <tbody>
              {transportadorasGerencial.map((row) => (
                <tr key={row.transportadora_nome} className="cursor-pointer" onClick={() => setTransportadoraId(transportadoras.find((t) => t.razao_social === row.transportadora_nome)?.id?.toString() || '')}>
                  <td>{row.transportadora_nome}</td>
                  <td>{row.quantidade_ctes}</td>
                  <td>{fmtMoney(row.valor_total_fretes)}</td>
                  <td>{fmtMoney(row.frete_medio)}</td>
                  <td>{(row.participacao_pct ?? 0).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="erp-card overflow-x-auto">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 p-4 pb-1">
            <h3 className="font-medium text-sm">Série de fretes</h3>
            <select className="erp-select w-full sm:w-auto" value={serieTipo} onChange={(e) => setSerieTipo(e.target.value as 'mensal' | 'trimestral')}>
              <option value="mensal">Mensal</option>
              <option value="trimestral">Trimestral</option>
            </select>
          </div>
          <table className="erp-table text-sm" data-mobile-table-mode="cards">
            <thead><tr><th>Período</th><th>Fretes</th><th>CT-es</th><th>Médio</th><th>Peso/Fat.</th></tr></thead>
            <tbody>
              {serieGerencial.map((row, idx) => (
                <tr
                  key={`${row.ano_mes ?? row.rotulo ?? idx}`}
                  className="cursor-pointer"
                  onClick={() => {
                    if (row.ano_mes) {
                      setPeriodoTipo('mes');
                      setMes(row.ano_mes);
                    } else if (row.ano && row.trimestre) {
                      setPeriodoTipo('trimestre');
                      setAnoTri(row.ano);
                      setNumTri(row.trimestre as 1 | 2 | 3 | 4);
                    }
                  }}
                >
                  <td>{row.ano_mes || row.rotulo || '—'}</td>
                  <td>{fmtMoney(row.totais.valor_total_fretes)}</td>
                  <td>{row.totais.quantidade_ctes}</td>
                  <td>{fmtMoney(row.totais.frete_medio)}</td>
                  <td>{(row.peso_frete_sobre_faturamento_pct ?? 0).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {loadError ? <ErrorState onRetry={() => void reloadList()} /> : null}
      {loadingList ? <TableSkeleton rows={6} cols={8} /> : null}
      {!loadingList && !loadError ? (
        <DataTableShell>
          <DataTable mobileMode="cards">
          <thead>
            <tr>
              <th>Emissão</th>
              <th>CT-e</th>
              <th>Chave</th>
              <th>Transportadora</th>
              <th>Tomador</th>
              <th>Valor</th>
              <th>Status</th>
              <th className="w-28">Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <EmptyState message="Nenhum XML de CT-e encontrado." />
                </td>
              </tr>
            ) : (
            items.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap text-sm">{r.dh_emissao?.slice(0, 16).replace('T', ' ')}</td>
                <td className="font-medium">{r.numero}/{r.serie}</td>
                <td className="font-mono text-xs" title={r.chave_acesso}>
                  {chaveNfeResumida(r.chave_acesso)}
                </td>
                <td className="max-w-[220px] truncate" title={r.transportadora_nome}>
                  {r.transportadora_nome || '—'}
                </td>
                <td className="max-w-[220px] truncate" title={r.empresa_tomadora_nome}>
                  {r.empresa_tomadora_nome || '—'}
                </td>
                <td>{fmtMoney(r.valor_total_servico)}</td>
                <td>
                  <div className="flex flex-col gap-1 items-start">
                    <StatusBadge status={statusCteHistorico(r.status_visual)} />
                    {r.status_conferencia ? (
                      <StatusBadge status={r.status_conferencia.toLowerCase()} />
                    ) : null}
                    <DfeClassificacaoBadges classificacao={r.classificacao_dfe} max={4} />
                  </div>
                </td>
                <td>
                  <div className="flex flex-col gap-1">
                    {mostraAcaoConferir(r.status_conferencia) ? (
                      <button
                        type="button"
                        className="erp-btn-primary erp-btn-sm"
                        onClick={() => abrirDetalhe(r, true)}
                      >
                        {labelAcaoConferencia(r.status_conferencia)}
                      </button>
                    ) : null}
                    <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => abrirDetalhe(r)}>
                      Detalhes
                    </button>
                    {r.tem_xml_conteudo ? (
                      <button
                        type="button"
                        className="erp-btn-outline erp-btn-sm inline-flex items-center justify-center"
                        title="Imprimir DACTE"
                        aria-label="Imprimir DACTE"
                        onClick={() => void imprimirDacte(r)}
                      >
                        <Printer className="h-4 w-4" />
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))
            )}
          </tbody>
          </DataTable>
        {count > 0 ? (
          <PaginationControls
            page={page}
            pageSize={pageSize}
            count={count}
            totalPages={totalPages}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        ) : null}
        </DataTableShell>
        ) : null}

      <CTeHistoricoDetalheModal
        open={modalDetalhe}
        cteId={detalheId}
        listRow={detalheRow}
        abaInicial={abaInicialConferencia ? 'conferencia' : 'resumo'}
        onClose={() => {
          setModalDetalhe(false);
          setDetalheId(null);
          setDetalheRow(null);
          setAbaInicialConferencia(false);
        }}
        onConferenciaAtualizada={() => void reloadList()}
      />
    </div>
  );
};

export default CTeHistoricoImportado;

