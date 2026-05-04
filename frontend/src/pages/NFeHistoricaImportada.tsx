import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileUp, FileCheck, Copy, AlertCircle, RefreshCw, Info } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import { clientesService } from '@/services/api/clientes';
import { empresasService } from '@/services/api/empresas';
import {
  nfeHistoricaImportadaService,
  type NFeHistoricaImportResultado,
  type NFeSaidaHistoricaDetalhe,
  type NFeSaidaHistoricaList,
} from '@/services/api/nfeHistoricaImportada';
import type { Cliente, Empresa } from '@/types';

const truncarChave = (chave: string) => {
  if (!chave) return '—';
  if (chave.length <= 16) return chave;
  return `${chave.slice(0, 8)}...${chave.slice(-8)}`;
};

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
  clienteId: string,
  empresaId: string,
  incluirCanceladas: boolean,
): URLSearchParams {
  const qs = new URLSearchParams();
  if (tipo === 'mes') qs.set('mes', mes);
  else if (tipo === 'trimestre') qs.set('trimestre', `${anoTri}-Q${numTri}`);
  else {
    qs.set('data_inicio', di);
    qs.set('data_fim', df);
  }
  if (clienteId) qs.set('cliente_id', clienteId);
  if (empresaId) qs.set('empresa_emitente_id', empresaId);
  if (incluirCanceladas) qs.set('incluir_canceladas', 'true');
  return qs;
}

const toNum = (v: unknown): number => {
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
};

const fmtMoney = (v: unknown): string => `R$ ${toNum(v).toFixed(2)}`;

const getIcmsTot = (totaisJson: Record<string, unknown> | undefined) => {
  const raw = totaisJson?.ICMSTot;
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) return raw as Record<string, unknown>;
  if (Array.isArray(raw) && raw[0] && typeof raw[0] === 'object') return raw[0] as Record<string, unknown>;
  return {};
};

const badgeStatusClass = (statusVisual: string) => {
  const s = (statusVisual || '').toLowerCase();
  if (s.includes('cancel')) return 'bg-destructive/10 text-destructive';
  if (s.includes('pend') || s.includes('erro')) return 'bg-amber-500/10 text-amber-700 dark:text-amber-400';
  return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400';
};

const NFeHistoricaImportada = () => {
  const [lista, setLista] = useState<NFeSaidaHistoricaList[]>([]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [ultimoResultado, setUltimoResultado] = useState<NFeHistoricaImportResultado | null>(null);
  const [erroUpload, setErroUpload] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<NFeSaidaHistoricaDetalhe | null>(null);
  const [modalDetalhe, setModalDetalhe] = useState(false);
  const [abaModal, setAbaModal] = useState<'resumo' | 'totais' | 'itens' | 'eventos' | 'tecnico'>('resumo');

  // filtros do histórico acumulado
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
  const [clienteId, setClienteId] = useState('');
  const [empresaId, setEmpresaId] = useState('');
  const [incluirCanceladas, setIncluirCanceladas] = useState(false);
  const [loadingHistorico, setLoadingHistorico] = useState(false);
  const [erroHistorico, setErroHistorico] = useState<string | null>(null);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);

  useEffect(() => {
    void (async () => {
      try {
        const [c, e] = await Promise.all([clientesService.getAll(), empresasService.getAll()]);
        setClientes(c);
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
      const qs = buildQuery(periodoTipo, mes, anoTri, numTri, di, df, clienteId, empresaId, incluirCanceladas);
      setLista(await nfeHistoricaImportadaService.list(qs));
    } catch (e) {
      setErroHistorico(apiErrorMessage(e));
      setLista([]);
    } finally {
      setLoadingHistorico(false);
    }
  }, [periodoTipo, mes, anoTri, numTri, di, df, clienteId, empresaId, incluirCanceladas]);

  useEffect(() => {
    void loadHistorico();
  }, [loadHistorico]);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setErroUpload(null);
    setBusy(true);
    try {
      const res = await nfeHistoricaImportadaService.importarXmls(Array.from(files));
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
      const d = await nfeHistoricaImportadaService.getById(id);
      setDetalhe(d);
      setAbaModal('resumo');
      setModalDetalhe(true);
    } catch (e) {
      setErroUpload(apiErrorMessage(e));
    }
  };

  const filtrados = lista.filter(
    (r) =>
      r.chave_acesso.includes(search) ||
      r.numero.includes(search) ||
      (r.cliente_nome || '').toLowerCase().includes(search.toLowerCase()),
  );

  const arquivosProcessados = useMemo(() => {
    if (!ultimoResultado) return [];
    const out = new Set<string>();
    ultimoResultado.importadas.forEach((x) => out.add(x.arquivo));
    ultimoResultado.duplicadas.forEach((x) => out.add(x.arquivo));
    ultimoResultado.eventos_aplicados.forEach((x) => out.add(x.arquivo));
    ultimoResultado.eventos_duplicados.forEach((x) => out.add(x.arquivo));
    ultimoResultado.erros.forEach((x) => out.add(x.arquivo));
    return Array.from(out).sort((a, b) => a.localeCompare(b));
  }, [ultimoResultado]);

  return (
    <div>
      <PageHeader title="NF-e histórica (importação XML)" searchValue={search} onSearch={setSearch} />

      <p className="text-sm text-muted-foreground mb-4">
        <Link to="/visao-gerencial-nfe-historica" className="text-primary underline-offset-4 hover:underline">
          Visão fiscal e apuração gerencial (consolidado das notas importadas)
        </Link>
      </p>

      <div className="erp-card p-6 mb-6 border-dashed border-2 border-border">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="flex-1">
            <h2 className="font-semibold text-foreground flex items-center gap-2">
              <FileUp className="h-5 w-5" />
              Importar XMLs de NF-e e eventos
            </h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
              Aceita XML principal da NF-e e XML de evento (ex.: cancelamento). Base exclusiva fiscal/gerencial:
              sem estoque, sem contas a receber e sem reemissão pelo ERP.
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

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="erp-card p-4 border-l-4 border-l-success">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Importadas</div>
            <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.importadas}</div>
            {ultimoResultado.importadas.length > 0 && (
              <ul className="mt-2 text-xs text-muted-foreground space-y-1 max-h-28 overflow-y-auto">
                {ultimoResultado.importadas.map((i) => (
                  <li key={i.chave_acesso}>
                    <FileCheck className="inline h-3 w-3 mr-1 text-success" />
                    {i.arquivo} — NF {i.numero}/{i.serie}
                  </li>
                ))}
              </ul>
            )}
          </div>
            <div className="erp-card p-4 border-l-4 border-l-muted-foreground">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Ignoradas (duplicidade)</div>
            <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.duplicadas}</div>
            {ultimoResultado.duplicadas.length > 0 && (
              <ul className="mt-2 text-xs text-muted-foreground space-y-1 max-h-28 overflow-y-auto">
                {ultimoResultado.duplicadas.map((d) => (
                  <li key={`${d.arquivo}-${d.chave_acesso}`}>
                    <Copy className="inline h-3 w-3 mr-1" />
                    {d.arquivo}: {d.mensagem}
                  </li>
                ))}
              </ul>
            )}
          </div>
            <div className="erp-card p-4 border-l-4 border-l-amber-500">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Eventos aplicados</div>
            <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.eventos_aplicados}</div>
            {ultimoResultado.eventos_aplicados.length > 0 && (
              <ul className="mt-2 text-xs text-muted-foreground space-y-1 max-h-28 overflow-y-auto">
                {ultimoResultado.eventos_aplicados.map((e) => (
                  <li key={`${e.arquivo}-${e.protocolo_evento}-${e.tipo_evento}`}>
                    <FileCheck className="inline h-3 w-3 mr-1 text-amber-600" />
                    {e.arquivo}: cancelamento aplicado na chave {e.chave_acesso}
                  </li>
                ))}
              </ul>
            )}
          </div>
            <div className="erp-card p-4 border-l-4 border-l-muted-foreground">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Eventos duplicados</div>
            <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.eventos_duplicados}</div>
            {ultimoResultado.eventos_duplicados.length > 0 && (
              <ul className="mt-2 text-xs text-muted-foreground space-y-1 max-h-28 overflow-y-auto">
                {ultimoResultado.eventos_duplicados.map((e) => (
                  <li key={`${e.arquivo}-${e.chave_acesso}-${e.tipo_evento}`}>
                    <Copy className="inline h-3 w-3 mr-1" />
                    {e.arquivo}: {e.mensagem}
                  </li>
                ))}
              </ul>
            )}
          </div>
            <div className="erp-card p-4 border-l-4 border-l-destructive">
            <div className="text-xs text-muted-foreground uppercase tracking-wide">Erros de leitura</div>
            <div className="text-2xl font-bold text-foreground">{ultimoResultado.resumo.erros}</div>
            {ultimoResultado.erros.length > 0 && (
              <ul className="mt-2 text-xs text-destructive space-y-1 max-h-28 overflow-y-auto">
                {ultimoResultado.erros.map((e) => (
                  <li key={e.arquivo}>
                    <AlertCircle className="inline h-3 w-3 mr-1" />
                    {e.arquivo}: {e.mensagem}
                  </li>
                ))}
              </ul>
            )}
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
            <strong className="text-foreground">Histórico de NF-e importadas</strong>: a grade abaixo é acumulada e
            reflete todas as notas já importadas no período filtrado (não apenas o último upload).
          </span>
        </p>

        <div className="flex flex-wrap gap-3 items-end mt-4">
          <div>
            <label className="erp-label">Período</label>
            <select
              className="erp-select mt-1 min-w-[160px]"
              value={periodoTipo}
              onChange={(e) => setPeriodoTipo(e.target.value as PeriodoTipo)}
            >
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
                <input
                  type="number"
                  className="erp-input mt-1 w-28"
                  value={anoTri}
                  onChange={(e) => setAnoTri(Number(e.target.value))}
                  min={2000}
                  max={2100}
                />
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
            <label className="erp-label">Cliente (vinculado)</label>
            <select className="erp-select mt-1 min-w-[200px]" value={clienteId} onChange={(e) => setClienteId(e.target.value)}>
              <option value="">Todos</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.razao_social}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="erp-label">Emitente (vinculado)</label>
            <select className="erp-select mt-1 min-w-[200px]" value={empresaId} onChange={(e) => setEmpresaId(e.target.value)}>
              <option value="">Todos</option>
              {empresas.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.razao_social}
                </option>
              ))}
            </select>
          </div>
          <label className="inline-flex items-center gap-2 mt-5 text-sm text-muted-foreground">
            <input type="checkbox" checked={incluirCanceladas} onChange={(e) => setIncluirCanceladas(e.target.checked)} />
            Incluir canceladas
          </label>
          <button type="button" className="erp-btn-primary mt-5" onClick={() => void loadHistorico()} disabled={loadingHistorico}>
            <RefreshCw className={`h-4 w-4 mr-1 inline ${loadingHistorico ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
        </div>
        {erroHistorico && <p className="text-sm text-destructive mt-3">{erroHistorico}</p>}
      </div>

      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Emissão</th>
              <th>NF</th>
              <th>Destinatário</th>
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
                <td>{r.cliente_nome || '—'}</td>
                <td>{fmtMoney(r.valor_total_nf)}</td>
                <td>
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${badgeStatusClass(r.status_visual)}`}>
                    {r.status_visual || 'autorizada'}
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
          <p className="p-6 text-sm text-muted-foreground text-center">Nenhuma nota no período/filtragem selecionados.</p>
        )}
      </div>

      <Modal isOpen={modalDetalhe} onClose={() => setModalDetalhe(false)} title="NF-e importada (histórico)" size="xl">
        {detalhe && (
          <div className="space-y-4 text-sm max-h-[70vh] overflow-y-auto">
            <div className="flex flex-wrap gap-2 border-b border-border pb-3">
              <button
                type="button"
                className={`erp-btn-sm ${abaModal === 'resumo' ? 'erp-btn-primary' : 'erp-btn-outline'}`}
                onClick={() => setAbaModal('resumo')}
              >
                Resumo da nota
              </button>
              <button
                type="button"
                className={`erp-btn-sm ${abaModal === 'totais' ? 'erp-btn-primary' : 'erp-btn-outline'}`}
                onClick={() => setAbaModal('totais')}
              >
                Totais fiscais
              </button>
              <button
                type="button"
                className={`erp-btn-sm ${abaModal === 'itens' ? 'erp-btn-primary' : 'erp-btn-outline'}`}
                onClick={() => setAbaModal('itens')}
              >
                Itens
              </button>
              <button
                type="button"
                className={`erp-btn-sm ${abaModal === 'eventos' ? 'erp-btn-primary' : 'erp-btn-outline'}`}
                onClick={() => setAbaModal('eventos')}
              >
                Eventos da NF-e
              </button>
              <button
                type="button"
                className={`erp-btn-sm ${abaModal === 'tecnico' ? 'erp-btn-primary' : 'erp-btn-outline'}`}
                onClick={() => setAbaModal('tecnico')}
              >
                Dados técnicos / XML
              </button>
            </div>

            {abaModal === 'resumo' && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <span className="text-muted-foreground">Chave</span>
                  <p className="font-mono text-xs break-all">{detalhe.chave_acesso}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">NF / Série</span>
                  <p>
                    {detalhe.numero}/{detalhe.serie}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Emissão</span>
                  <p>{detalhe.dh_emissao?.replace('T', ' ').slice(0, 19) || '—'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Destinatário</span>
                  <p>{detalhe.cliente_nome || '—'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Empresa (ERP) no documento</span>
                  <p>
                    {detalhe.empresa_nome || '—'} {detalhe.papel_empresa ? `(${detalhe.papel_empresa})` : ''}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Valor total</span>
                  <p>{fmtMoney(detalhe.valor_total_nf)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Protocolo</span>
                  <p>{detalhe.protocolo || '—'}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Status efetivo</span>
                  <p>{detalhe.status_visual || detalhe.status_documento || (detalhe.cancelada ? 'cancelada' : 'autorizada')}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">cStat / motivo efetivo</span>
                  <p>
                    {detalhe.cstat_visual || '—'} {detalhe.motivo_visual ? `— ${detalhe.motivo_visual}` : ''}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Cancelamento</span>
                  <p>
                    Data: {detalhe.data_cancelamento?.replace('T', ' ').slice(0, 19) || '—'} | Prot:{' '}
                    {detalhe.protocolo_cancelamento || detalhe.protocolo_evento || '—'}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Flags</span>
                  <p>
                    importada / externa / histórica / cancelada: {String(detalhe.importada)} / {String(detalhe.origem_externa)} /{' '}
                    {String(detalhe.historica)} / {String(detalhe.cancelada)}
                  </p>
                </div>
              </div>
            )}

            {abaModal === 'totais' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Valor dos produtos</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.valor_produtos)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Valor total da nota</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.valor_total_nf)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Frete</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.v_frete)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Desconto</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.v_desc)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">Outras despesas</div>
                  <div className="text-lg font-semibold">{fmtMoney(detalhe.v_outro)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">ICMS</div>
                  <div className="text-lg font-semibold">{fmtMoney(getIcmsTot(detalhe.totais_json).vICMS)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">IPI</div>
                  <div className="text-lg font-semibold">{fmtMoney(getIcmsTot(detalhe.totais_json).vIPI)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">PIS</div>
                  <div className="text-lg font-semibold">{fmtMoney(getIcmsTot(detalhe.totais_json).vPIS)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">COFINS</div>
                  <div className="text-lg font-semibold">{fmtMoney(getIcmsTot(detalhe.totais_json).vCOFINS)}</div>
                </div>
                <div className="erp-card p-3">
                  <div className="text-xs text-muted-foreground">ST (se houver)</div>
                  <div className="text-lg font-semibold">{fmtMoney(getIcmsTot(detalhe.totais_json).vST)}</div>
                </div>
              </div>
            )}

            {abaModal === 'itens' && (
              <div className="space-y-3">
                <span className="text-muted-foreground font-medium">Itens ({detalhe.itens?.length ?? 0})</span>
                <div className="erp-card overflow-x-auto">
                  <table className="erp-table text-xs">
                    <thead>
                      <tr>
                        <th>Descrição</th>
                        <th>NCM</th>
                        <th>CFOP</th>
                        <th>Qtd</th>
                        <th>UN</th>
                        <th>Vlr unit.</th>
                        <th>Vlr total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(detalhe.itens || []).map((it) => {
                        const prod = it.prod_json || {};
                        return (
                          <tr key={it.id}>
                            <td className="max-w-[220px] truncate" title={String(prod.xProd || '—')}>
                              {String(prod.xProd || '—')}
                            </td>
                            <td>{String(prod.NCM || '—')}</td>
                            <td>{String(prod.CFOP || '—')}</td>
                            <td>{String(prod.qCom || '—')}</td>
                            <td>{String(prod.uCom || '—')}</td>
                            <td>{fmtMoney(prod.vUnCom)}</td>
                            <td>{fmtMoney(prod.vProd)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {(detalhe.itens || []).map((it) => (
                  <details key={`fiscal-${it.id}`} className="erp-card p-3">
                    <summary className="cursor-pointer font-medium">Detalhes fiscais do item {it.n_item}</summary>
                    <pre className="text-xs overflow-x-auto max-h-48 mt-2 text-muted-foreground">
                      {JSON.stringify(it.imposto_json, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            )}

            {abaModal === 'eventos' && (
              <div className="space-y-3">
                <span className="text-muted-foreground font-medium">
                  Eventos da NF-e ({detalhe.eventos?.length ?? 0})
                </span>
                {(!detalhe.eventos || detalhe.eventos.length === 0) && (
                  <p className="text-sm text-muted-foreground">Nenhum evento foi importado para esta nota.</p>
                )}
                {detalhe.eventos && detalhe.eventos.length > 0 && (
                  <div className="erp-card overflow-x-auto">
                    <table className="erp-table text-xs">
                      <thead>
                        <tr>
                          <th>Tipo evento</th>
                          <th>Protocolo</th>
                          <th>Data</th>
                          <th>Arquivo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detalhe.eventos.map((ev) => (
                          <tr key={ev.id}>
                            <td>{ev.tipo_evento}</td>
                            <td>{ev.protocolo_evento || '—'}</td>
                            <td>{ev.data_evento ? ev.data_evento.replace('T', ' ').slice(0, 19) : '—'}</td>
                            <td className="max-w-[200px] truncate" title={ev.nome_arquivo}>
                              {ev.nome_arquivo || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {detalhe.eventos?.map((ev) => (
                  <details key={`evento-${ev.id}`} className="erp-card p-3">
                    <summary className="cursor-pointer font-medium">
                      Evento {ev.tipo_evento} — protocolo {ev.protocolo_evento || '—'}
                    </summary>
                    <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                      {JSON.stringify(ev.evento_json, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            )}

            {abaModal === 'tecnico' && (
              <div className="space-y-3">
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">totais_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                    {JSON.stringify(detalhe.totais_json, null, 2)}
                  </pre>
                </details>
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">prot_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                    {JSON.stringify(detalhe.prot_json, null, 2)}
                  </pre>
                </details>
                <details className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">reforma_e_outros_json</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                    {JSON.stringify(detalhe.reforma_e_outros_json, null, 2)}
                  </pre>
                </details>
                {detalhe.evento_cancelamento_json && Object.keys(detalhe.evento_cancelamento_json).length > 0 && (
                  <details className="erp-card p-3">
                    <summary className="cursor-pointer font-medium">evento_cancelamento_json</summary>
                    <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                      {JSON.stringify(detalhe.evento_cancelamento_json, null, 2)}
                    </pre>
                  </details>
                )}
                {(detalhe.itens || []).map((it) => (
                  <details key={`raw-item-${it.id}`} className="erp-card p-3">
                    <summary className="cursor-pointer font-medium">Item {it.n_item} — prod_json / imposto_json</summary>
                    <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                      {JSON.stringify(it.prod_json, null, 2)}
                    </pre>
                    <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                      {JSON.stringify(it.imposto_json, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default NFeHistoricaImportada;
