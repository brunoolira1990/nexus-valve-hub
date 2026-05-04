import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, FileCheck, FileUp, Info, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import { empresasService } from '@/services/api/empresas';
import { transportadorasService } from '@/services/api/transportadoras';
import type { Empresa, Transportadora } from '@/types';
import {
  cteHistoricoImportadoService,
  type CTeHistImportResultado,
  type CTeHistoricoDetalhe,
  type CTeHistoricoList,
  type CTeResumoGerencial,
  type CTeSerieGerencial,
  type CTeTransportadoraGerencial,
} from '@/services/api/cteHistoricoImportado';

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

const truncarChave = (chave: string) => {
  if (!chave) return '—';
  if (chave.length <= 16) return chave;
  return `${chave.slice(0, 8)}...${chave.slice(-8)}`;
};

const toNum = (v: unknown): number => {
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
};

const fmtMoney = (v: unknown): string => `R$ ${toNum(v).toFixed(2)}`;

const badgeStatusClass = (statusVisual: string) => {
  const s = (statusVisual || '').toLowerCase();
  if (s.includes('cancel')) return 'bg-destructive/10 text-destructive';
  if (s.includes('pend') || s.includes('erro')) return 'bg-amber-500/10 text-amber-700 dark:text-amber-400';
  return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400';
};

const CTeHistoricoImportado = () => {
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [ultimoResultado, setUltimoResultado] = useState<CTeHistImportResultado | null>(null);
  const [erroUpload, setErroUpload] = useState<string | null>(null);

  const [lista, setLista] = useState<CTeHistoricoList[]>([]);
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

  const [resumoGerencial, setResumoGerencial] = useState<CTeResumoGerencial | null>(null);
  const [transportadorasGerencial, setTransportadorasGerencial] = useState<CTeTransportadoraGerencial[]>([]);
  const [serieGerencial, setSerieGerencial] = useState<CTeSerieGerencial[]>([]);

  const [detalhe, setDetalhe] = useState<CTeHistoricoDetalhe | null>(null);
  const [modalDetalhe, setModalDetalhe] = useState(false);
  const [abaModal, setAbaModal] = useState<'resumo' | 'participantes' | 'totais' | 'docs' | 'eventos' | 'tecnico'>('resumo');

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

  const loadHistorico = useCallback(async () => {
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
      const [listaData, resumo, porTransportadora, serieMensal, serieTrimestral] = await Promise.all([
        cteHistoricoImportadoService.list(qs),
        cteHistoricoImportadoService.resumoGerencial(qs),
        cteHistoricoImportadoService.transportadorasGerencial(qs),
        cteHistoricoImportadoService.serieMensalGerencial(qs),
        cteHistoricoImportadoService.serieTrimestralGerencial(qs),
      ]);
      setLista(listaData);
      setResumoGerencial(resumo);
      setTransportadorasGerencial(porTransportadora.transportadoras);
      setSerieGerencial(serieTipo === 'mensal' ? serieMensal.meses : serieTrimestral.trimestres);
    } catch (e) {
      setErroHistorico(apiErrorMessage(e));
      setLista([]);
      setResumoGerencial(null);
      setTransportadorasGerencial([]);
      setSerieGerencial([]);
    } finally {
      setLoadingHistorico(false);
    }
  }, [periodoTipo, mes, anoTri, numTri, di, df, transportadoraId, empresaTomadoraId, incluirCancelados, modalFiltro, tipoServicoFiltro, serieTipo]);

  useEffect(() => {
    void loadHistorico();
  }, [loadHistorico]);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setErroUpload(null);
    setBusy(true);
    try {
      const res = await cteHistoricoImportadoService.importarXmls(Array.from(files));
      setUltimoResultado(res);
      await loadHistorico();
    } catch (e) {
      setErroUpload(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const abrirDetalhe = async (id: number) => {
    try {
      const d = await cteHistoricoImportadoService.getById(id);
      setDetalhe(d);
      setAbaModal('resumo');
      setModalDetalhe(true);
    } catch (e) {
      setErroUpload(apiErrorMessage(e));
    }
  };

  const filtrados = lista.filter(
    (r) =>
      r.numero.includes(search) ||
      r.chave_acesso.includes(search) ||
      (r.transportadora_nome || '').toLowerCase().includes(search.toLowerCase()) ||
      (r.empresa_tomadora_nome || '').toLowerCase().includes(search.toLowerCase()),
  );

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
      <PageHeader title="CT-e histórico (importação XML)" searchValue={search} onSearch={setSearch} />

      <p className="text-sm text-muted-foreground mb-4">
        <Link to="/cte-entrada" className="text-primary underline-offset-4 hover:underline">
          Ir para CT-e de entrada (operacional)
        </Link>
      </p>

      <div className="erp-card p-6 mb-6 border-dashed border-2 border-border">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="flex-1">
            <h2 className="font-semibold text-foreground flex items-center gap-2">
              <FileUp className="h-5 w-5" />
              Importar XMLs de CT-e
            </h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              Base histórica fiscal/logística/gerencial. Não gera rateio operacional, contas a pagar, contábil nem vínculo obrigatório com NF-e operacional.
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
      </div>

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

      <div className="erp-card p-4 mb-4">
        <p className="text-sm text-muted-foreground flex gap-2 items-start">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            <strong className="text-foreground">Histórico de CT-e importados</strong>: a grade abaixo é acumulada e reflete todos os CT-es já importados no período filtrado.
          </span>
        </p>

        <div className="flex flex-wrap gap-3 items-end mt-4">
          <div>
            <label className="erp-label">Período</label>
            <select className="erp-select mt-1 min-w-[160px]" value={periodoTipo} onChange={(e) => setPeriodoTipo(e.target.value as PeriodoTipo)}>
              <option value="mes">Mês</option>
              <option value="trimestre">Trimestre</option>
              <option value="intervalo">Data inicial / final</option>
            </select>
          </div>
          {periodoTipo === 'mes' && (
            <div>
              <label className="erp-label">Mês</label>
              <input type="month" className="erp-input mt-1" value={mes} onChange={(e) => setMes(e.target.value)} />
            </div>
          )}
          {periodoTipo === 'trimestre' && (
            <>
              <div>
                <label className="erp-label">Ano</label>
                <input type="number" className="erp-input mt-1 w-28" value={anoTri} onChange={(e) => setAnoTri(Number(e.target.value))} min={2000} max={2100} />
              </div>
              <div>
                <label className="erp-label">Trimestre</label>
                <select className="erp-select mt-1" value={numTri} onChange={(e) => setNumTri(Number(e.target.value) as 1 | 2 | 3 | 4)}>
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
                <input type="date" className="erp-input mt-1" value={di} onChange={(e) => setDi(e.target.value)} />
              </div>
              <div>
                <label className="erp-label">Fim</label>
                <input type="date" className="erp-input mt-1" value={df} onChange={(e) => setDf(e.target.value)} />
              </div>
            </>
          )}
          <div>
            <label className="erp-label">Transportadora</label>
            <select className="erp-select mt-1 min-w-[220px]" value={transportadoraId} onChange={(e) => setTransportadoraId(e.target.value)}>
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
            <select className="erp-select mt-1 min-w-[220px]" value={empresaTomadoraId} onChange={(e) => setEmpresaTomadoraId(e.target.value)}>
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
            <input className="erp-input mt-1 min-w-[100px]" placeholder="Ex.: 01" value={modalFiltro} onChange={(e) => setModalFiltro(e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Tipo serviço</label>
            <input className="erp-input mt-1 min-w-[100px]" placeholder="Ex.: 0" value={tipoServicoFiltro} onChange={(e) => setTipoServicoFiltro(e.target.value)} />
          </div>
          <label className="inline-flex items-center gap-2 mt-5 text-sm text-muted-foreground">
            <input type="checkbox" checked={incluirCancelados} onChange={(e) => setIncluirCancelados(e.target.checked)} />
            Incluir cancelados
          </label>
          <button type="button" className="erp-btn-primary mt-5" onClick={() => void loadHistorico()} disabled={loadingHistorico}>
            <RefreshCw className={`h-4 w-4 mr-1 inline ${loadingHistorico ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
        </div>
        {erroHistorico && <p className="text-sm text-destructive mt-3">{erroHistorico}</p>}
      </div>

      {resumoGerencial && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Fretes no período</div><div className="font-semibold">{fmtMoney(resumoGerencial.totais.valor_total_fretes)}</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">CT-es válidos</div><div className="font-semibold">{resumoGerencial.totais.quantidade_ctes}</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Frete médio</div><div className="font-semibold">{fmtMoney(resumoGerencial.totais.frete_medio)}</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Peso sobre faturamento</div><div className="font-semibold">{(resumoGerencial.indicadores_gerenciais.peso_frete_sobre_faturamento_pct ?? 0).toFixed(2)}%</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Peso sobre compras</div><div className="font-semibold">{(resumoGerencial.indicadores_gerenciais.peso_frete_sobre_compras_pct ?? 0).toFixed(2)}%</div></div>
          <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Faturamento base</div><div className="font-semibold">{fmtMoney(resumoGerencial.base_comparativa.faturamento)}</div></div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="erp-card overflow-x-auto">
          <h3 className="font-medium text-sm p-4 pb-1">Fretes por transportadora</h3>
          <table className="erp-table text-sm">
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
          <div className="flex items-center justify-between p-4 pb-1">
            <h3 className="font-medium text-sm">Série de fretes</h3>
            <select className="erp-select" value={serieTipo} onChange={(e) => setSerieTipo(e.target.value as 'mensal' | 'trimestral')}>
              <option value="mensal">Mensal</option>
              <option value="trimestral">Trimestral</option>
            </select>
          </div>
          <table className="erp-table text-sm">
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

      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Emissão</th>
              <th>CT-e</th>
              <th>Transportadora</th>
              <th>Tomador</th>
              <th>Valor</th>
              <th>Status</th>
              <th className="w-28">Ações</th>
            </tr>
          </thead>
          <tbody>
            {filtrados.map((r) => (
              <tr key={r.id}>
                <td className="whitespace-nowrap text-sm">{r.dh_emissao?.slice(0, 16).replace('T', ' ')}</td>
                <td className="font-medium">
                  {r.numero}/{r.serie}
                  <div className="font-mono text-[11px] text-muted-foreground" title={r.chave_acesso}>
                    {truncarChave(r.chave_acesso)}
                  </div>
                </td>
                <td className="max-w-[220px] truncate" title={r.transportadora_nome}>
                  {r.transportadora_nome || '—'}
                </td>
                <td className="max-w-[220px] truncate" title={r.empresa_tomadora_nome}>
                  {r.empresa_tomadora_nome || '—'}
                </td>
                <td>{fmtMoney(r.valor_total_servico)}</td>
                <td>
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${badgeStatusClass(r.status_visual)}`}>
                    {r.status_visual || 'autorizado'}
                  </span>
                </td>
                <td>
                  <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => void abrirDetalhe(r.id)}>
                    Detalhes
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtrados.length === 0 && !loadingHistorico && (
          <p className="p-6 text-sm text-muted-foreground text-center">Nenhum CT-e no período/filtragem selecionados.</p>
        )}
      </div>

      <Modal isOpen={modalDetalhe} onClose={() => setModalDetalhe(false)} title="CT-e importado (histórico)" size="xl">
        {detalhe && (
          <div className="space-y-4 text-sm max-h-[70vh] overflow-y-auto">
            <div className="flex flex-wrap gap-2 border-b border-border pb-3">
              <button type="button" className={`erp-btn-sm ${abaModal === 'resumo' ? 'erp-btn-primary' : 'erp-btn-outline'}`} onClick={() => setAbaModal('resumo')}>
                Resumo
              </button>
              <button type="button" className={`erp-btn-sm ${abaModal === 'participantes' ? 'erp-btn-primary' : 'erp-btn-outline'}`} onClick={() => setAbaModal('participantes')}>
                Participantes
              </button>
              <button type="button" className={`erp-btn-sm ${abaModal === 'totais' ? 'erp-btn-primary' : 'erp-btn-outline'}`} onClick={() => setAbaModal('totais')}>
                Totais / tributos
              </button>
              <button type="button" className={`erp-btn-sm ${abaModal === 'docs' ? 'erp-btn-primary' : 'erp-btn-outline'}`} onClick={() => setAbaModal('docs')}>
                Documentos vinculados
              </button>
              <button type="button" className={`erp-btn-sm ${abaModal === 'eventos' ? 'erp-btn-primary' : 'erp-btn-outline'}`} onClick={() => setAbaModal('eventos')}>
                Eventos
              </button>
              <button type="button" className={`erp-btn-sm ${abaModal === 'tecnico' ? 'erp-btn-primary' : 'erp-btn-outline'}`} onClick={() => setAbaModal('tecnico')}>
                Técnico / XML
              </button>
            </div>

            {abaModal === 'resumo' && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <span className="text-muted-foreground">Chave</span>
                  <p className="font-mono text-xs break-all">{detalhe.chave_acesso}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">CT-e</span>
                  <p>
                    {detalhe.numero}/{detalhe.serie} — mod {detalhe.modelo || '—'}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Emissão</span>
                  <p>{detalhe.dh_emissao?.replace('T', ' ').slice(0, 19) || '—'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Modal / serviço</span>
                  <p>
                    {detalhe.modal || '—'} / {detalhe.tipo_servico || '—'}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Origem → destino</span>
                  <p>
                    {detalhe.municipio_inicio || '—'}-{detalhe.uf_inicio || '—'} → {detalhe.municipio_fim || '—'}-{detalhe.uf_fim || '—'}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Valor total / a receber</span>
                  <p>
                    {fmtMoney(detalhe.valor_total_servico)} / {fmtMoney(detalhe.valor_receber)}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Status efetivo</span>
                  <p>
                    {detalhe.status_visual || detalhe.status_documento || '—'} — {detalhe.cstat_visual || detalhe.cstat || '—'}{' '}
                    {detalhe.motivo_visual ? `— ${detalhe.motivo_visual}` : ''}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Protocolo</span>
                  <p>{detalhe.protocolo || '—'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Empresa identificada</span>
                  <p>
                    {detalhe.empresa_nome || '—'} {detalhe.papel_empresa ? `(${detalhe.papel_empresa})` : ''}
                  </p>
                </div>
              </div>
            )}

            {abaModal === 'participantes' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Emitente (transportadora)</div>
                  <div className="text-sm font-medium">{detalhe.transportadora_nome || (detalhe.emit_json?.xNome as string) || '—'}</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.emit_json, null, 2)}</pre>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Tomador</div>
                  <div className="text-sm font-medium">{detalhe.empresa_tomadora_nome || '—'}</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.tomador_json, null, 2)}</pre>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Remetente</div>
                  <div className="text-sm font-medium">{detalhe.fornecedor_remetente_nome || '—'}</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.rem_json, null, 2)}</pre>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Destinatário</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.dest_json, null, 2)}</pre>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Expedidor</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.exped_json, null, 2)}</pre>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Recebedor</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.receb_json, null, 2)}</pre>
                </div>
              </div>
            )}

            {abaModal === 'totais' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Valor total do serviço</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.valor_total_servico)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Valor a receber</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.valor_receber)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">ICMS</div>
                  <div className="text-sm font-medium">
                    Base {fmtMoney(detalhe.icms_base)} | Aliq {toNum(detalhe.icms_aliquota).toFixed(4)}% | Valor {fmtMoney(detalhe.icms_valor)}
                  </div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Componentes do frete</div>
                  <pre className="mt-2 text-xs overflow-x-auto max-h-40 bg-muted rounded-md p-2">{JSON.stringify(detalhe.componentes_frete_json, null, 2)}</pre>
                </div>
              </div>
            )}

            {abaModal === 'docs' && (
              <div className="space-y-3">
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Chaves de NF-e referenciadas</div>
                  {(detalhe.chaves_nfe_vinculadas || []).length === 0 ? (
                    <p className="text-sm text-muted-foreground mt-2">Nenhuma chave de NF-e encontrada no XML.</p>
                  ) : (
                    <ul className="mt-2 text-xs font-mono text-muted-foreground space-y-1 max-h-48 overflow-y-auto">
                      {detalhe.chaves_nfe_vinculadas.map((k) => (
                        <li key={k} title={k}>
                          {truncarChave(k)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}

            {abaModal === 'eventos' && (
              <div className="space-y-3">
                <span className="text-muted-foreground font-medium">Eventos ({detalhe.eventos?.length ?? 0})</span>
                {(!detalhe.eventos || detalhe.eventos.length === 0) && (
                  <p className="text-sm text-muted-foreground">Nenhum evento foi importado para este CT-e (base pronta para evolução futura).</p>
                )}
                {detalhe.eventos?.map((ev) => (
                  <details key={`evento-${ev.id}`} className="erp-card p-3">
                    <summary className="cursor-pointer font-medium">
                      Evento {ev.tipo_evento} — protocolo {ev.protocolo_evento || '—'}
                    </summary>
                    <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">{JSON.stringify(ev.evento_json, null, 2)}</pre>
                  </details>
                ))}
              </div>
            )}

            {abaModal === 'tecnico' && (
              <div className="space-y-3">
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">totais_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">{JSON.stringify(detalhe.totais_json, null, 2)}</pre>
                </details>
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">imposto_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">{JSON.stringify(detalhe.imposto_json, null, 2)}</pre>
                </details>
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">prot_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">{JSON.stringify(detalhe.prot_json, null, 2)}</pre>
                </details>
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">reforma_e_outros_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">{JSON.stringify(detalhe.reforma_e_outros_json, null, 2)}</pre>
                </details>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default CTeHistoricoImportado;

