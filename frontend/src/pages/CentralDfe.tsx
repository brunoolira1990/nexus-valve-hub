import { useCallback, useEffect, useMemo, useState } from 'react';
import { CloudDownload, Copy, ExternalLink, Eye, Inbox, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { CTeHistoricoDetalheModal } from '@/components/fiscal/CTeHistoricoDetalheModal';
import { FilterBar } from '@/components/list/FilterBar';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { PageHeader } from '@/components/PageHeader';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { NexusCard } from '@/components/nexus/NexusCard';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useAppContexto } from '@/hooks/useAppContexto';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import {
  centralDfeService,
  type CentralDfeCapturaResponse,
  type CentralDfeDocumento,
  type CentralDfeListResponse,
  type CentralDfeResumo,
} from '@/services/api/centralDfe';
import { apiErrorMessage } from '@/services/api/config';
import { copiarTextoParaAreaDeTransferencia } from '@/utils/nfeXmlImportDiagnostico';

const fmtMoney = (v: string | number | null | undefined): string => {
  const n = Number(String(v ?? '0').replace(',', '.'));
  return `R$ ${Number.isFinite(n) ? n.toFixed(2) : '0.00'}`;
};

const fmtData = (v: string | null | undefined): string => {
  if (!v) return '—';
  const d = v.slice(0, 10);
  const [y, m, day] = d.split('-');
  if (!y || !m || !day) return v;
  return `${day}/${m}/${y}`;
};

const fmtCnpj = (cnpj: string): string => {
  const d = (cnpj || '').replace(/\D/g, '');
  if (d.length !== 14) return cnpj || '—';
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
};

function statusEntradaBadge(status: string): string {
  const map: Record<string, string> = {
    PENDENTE_ENTRADA: 'pendente',
    IMPORTADO_BASE: 'importado',
    CONFERIDO: 'conferida',
    PREPARADO: 'preparada',
    DIVERGENTE: 'divergente',
    IGNORADO: 'ignorada',
    JA_LANCADO: 'processado',
  };
  return map[status] || 'pendente';
}

function KpiCard({ label, value }: { label: string; value: number }) {
  return (
    <NexusCard className="p-4">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-semibold mt-1 tabular-nums">{value}</p>
    </NexusCard>
  );
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function ultimoDiaMes(ano: number, mes: number): number {
  return new Date(ano, mes, 0).getDate();
}

function intervaloMes(ano: number, mes: number): { inicio: string; fim: string } {
  const fim = ultimoDiaMes(ano, mes);
  return {
    inicio: `${ano}-${pad2(mes)}-01`,
    fim: `${ano}-${pad2(mes)}-${pad2(fim)}`,
  };
}

function intervaloMesAtual(): { inicio: string; fim: string } {
  const hoje = new Date();
  return intervaloMes(hoje.getFullYear(), hoje.getMonth() + 1);
}

function intervaloMesAnterior(): { inicio: string; fim: string } {
  const hoje = new Date();
  const mes = hoje.getMonth();
  const ano = mes === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear();
  const mesRef = mes === 0 ? 12 : mes;
  return intervaloMes(ano, mesRef);
}

function aplicarCompetenciaMmAaaa(valor: string): { inicio: string; fim: string } | null {
  const limpo = valor.replace(/\D/g, '');
  if (limpo.length !== 6) return null;
  const mes = Number(limpo.slice(0, 2));
  const ano = Number(limpo.slice(2));
  if (mes < 1 || mes > 12) return null;
  return intervaloMes(ano, mes);
}

const CentralDfe = () => {
  const { contexto } = useAppContexto();
  const empresaId = contexto?.empresa?.id;

  const [resumo, setResumo] = useState<CentralDfeResumo | null>(null);
  const [empresaInfo, setEmpresaInfo] = useState<CentralDfeListResponse['empresa'] | null>(null);
  const [dataEmissaoInicio, setDataEmissaoInicio] = useState('');
  const [dataEmissaoFim, setDataEmissaoFim] = useState('');
  const [competenciaEmissao, setCompetenciaEmissao] = useState('');
  const [chaveFiltro, setChaveFiltro] = useState('');
  const [limiteLotesCaptura, setLimiteLotesCaptura] = useState(3);
  const [copiadoId, setCopiadoId] = useState<number | null>(null);
  const [detalheRow, setDetalheRow] = useState<CentralDfeDocumento | null>(null);
  const [modalCteOpen, setModalCteOpen] = useState(false);
  const [modalCapturaOpen, setModalCapturaOpen] = useState(false);
  const [capturando, setCapturando] = useState(false);

  const extraFilters = useMemo(() => {
    const f: Record<string, string> = { ordering: '-data_emissao' };
    if (empresaId) f.empresa_id = String(empresaId);
    if (dataEmissaoInicio) f.data_emissao_inicio = dataEmissaoInicio;
    if (dataEmissaoFim) f.data_emissao_fim = dataEmissaoFim;
    if (!dataEmissaoInicio && !dataEmissaoFim && competenciaEmissao) {
      f.competencia_emissao = competenciaEmissao.replace(/\D/g, '').length === 6
        ? competenciaEmissao.replace(/\D/g, '')
        : competenciaEmissao;
    }
    if (chaveFiltro) f.chave_acesso = chaveFiltro.replace(/\D/g, '');
    return f;
  }, [empresaId, dataEmissaoInicio, dataEmissaoFim, competenciaEmissao, chaveFiltro]);

  const fetchPage = useCallback(
    async (params: Parameters<typeof centralDfeService.listPaginated>[0]) => {
      const data = await centralDfeService.listPaginated(params);
      setResumo(data.resumo ?? null);
      setEmpresaInfo(data.empresa ?? null);
      return data;
    },
    [],
  );

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
    filters,
    setFilter,
    setFilters,
    loading,
    error,
    reload,
  } = usePaginatedList<CentralDfeDocumento>({
    fetchPage,
    initialFilters: extraFilters,
  });

  useEffect(() => {
    setFilters((prev) => {
      const next = { ...prev };
      Object.entries(extraFilters).forEach(([k, v]) => {
        next[k] = v;
      });
      ['empresa_id', 'data_emissao_inicio', 'data_emissao_fim', 'competencia_emissao', 'chave_acesso', 'ordering'].forEach((k) => {
        if (!extraFilters[k]) delete next[k];
      });
      return next;
    });
  }, [extraFilters, setFilters]);

  const filterDefs = useMemo(
    () => [
      {
        key: 'tipo_documento',
        label: 'Tipo',
        value: filters.tipo_documento ?? '',
        options: [
          { value: 'NFE_ENTRADA', label: 'NF-e Fornecedor' },
          { value: 'CTE', label: 'CT-e Transportadora' },
        ],
      },
      {
        key: 'status_entrada',
        label: 'Status entrada',
        value: filters.status_entrada ?? '',
        options: [
          { value: 'PENDENTE_ENTRADA', label: 'Pendente de entrada' },
          { value: 'IMPORTADO_BASE', label: 'Importado — base DF-e' },
          { value: 'CONFERIDO', label: 'Conferido' },
          { value: 'DIVERGENTE', label: 'Divergente' },
          { value: 'IGNORADO', label: 'Ignorado' },
          { value: 'JA_LANCADO', label: 'Já lançado' },
        ],
      },
      {
        key: 'incluir_tratados',
        label: 'Tratados',
        value: filters.incluir_tratados ?? '',
        options: [{ value: 'true', label: 'Incluir já tratados' }],
      },
    ],
    [filters],
  );

  const abrirDetalhe = (row: CentralDfeDocumento) => {
    setDetalheRow(row);
    if (row.tipo_documento === 'CTE') {
      setModalCteOpen(true);
      return;
    }
    if (row.detalhe_rota) {
      window.location.assign(row.detalhe_rota);
    }
  };

  const copiarChave = async (row: CentralDfeDocumento) => {
    if (!row.chave_acesso) return;
    await copiarTextoParaAreaDeTransferencia(row.chave_acesso);
    setCopiadoId(row.id);
    window.setTimeout(() => setCopiadoId(null), 2000);
  };

  const empresaLabel = empresaInfo?.razao_social || contexto?.empresa?.nome_exibicao || 'empresa ativa';

  const aplicarPeriodoEmissao = (inicio: string, fim: string) => {
    setCompetenciaEmissao('');
    setDataEmissaoInicio(inicio);
    setDataEmissaoFim(fim);
  };

  const aplicarCompetencia = () => {
    const periodo = aplicarCompetenciaMmAaaa(competenciaEmissao);
    if (!periodo) {
      toast.error('Informe a competência no formato mm/aaaa (ex.: 06/2026).');
      return;
    }
    setDataEmissaoInicio(periodo.inicio);
    setDataEmissaoFim(periodo.fim);
  };

  const limparPeriodoEmissao = () => {
    setDataEmissaoInicio('');
    setDataEmissaoFim('');
    setCompetenciaEmissao('');
  };

  const periodoFiltroLabel = useMemo(() => {
    if (dataEmissaoInicio || dataEmissaoFim) {
      const de = dataEmissaoInicio ? fmtData(dataEmissaoInicio) : '…';
      const ate = dataEmissaoFim ? fmtData(dataEmissaoFim) : '…';
      return `emissão de ${de} até ${ate}`;
    }
    if (competenciaEmissao) return `competência ${competenciaEmissao}`;
    return 'sem filtro de emissão';
  }, [dataEmissaoInicio, dataEmissaoFim, competenciaEmissao]);

  const exibirResumoCaptura = (data: CentralDfeCapturaResponse) => {
    if (!data.sefaz_consultada) {
      const erros = data.erros ?? [];
      const msgCert = erros.find((e) => /certificado/i.test(e));
      if (msgCert) {
        toast.error('Certificado digital não disponível/configurado para consulta DF-e.');
      } else if (erros.length) {
        erros.forEach((e) => toast.error(e));
      } else {
        toast.error('A consulta SEFAZ não foi realizada. Verifique permissões e configuração.');
      }
      return;
    }

    const r = data.resumo;
    const sefaz = data.sefaz_por_tipo ?? {};
    const nfeSefaz = sefaz.NFE;
    const cteSefaz = sefaz.CTE;

    const linhasSefaz: string[] = [];
    if (nfeSefaz?.consultada) {
      linhasSefaz.push(
        `NF-e SEFAZ cStat ${nfeSefaz.cstat || '—'}: ${nfeSefaz.encontrados_xml} XML, ${nfeSefaz.novos} nova(s), ${nfeSefaz.duplicados} duplicada(s)`,
      );
    }
    if (cteSefaz?.consultada) {
      linhasSefaz.push(
        `CT-e SEFAZ cStat ${cteSefaz.cstat || '—'}: ${cteSefaz.encontrados_xml} XML, ${cteSefaz.novos} novo(s), ${cteSefaz.duplicados} duplicado(s)`,
      );
    }

    const nsuNfe = data.nsu_por_tipo?.NFE;
    const nsuCte = data.nsu_por_tipo?.CTE;
    if (nsuNfe) {
      linhasSefaz.push(
        `NSU NF-e: ${nsuNfe.ultimo_nsu_inicial ?? '—'} → ${nsuNfe.ultimo_nsu_final ?? nsuNfe.ultimo_nsu ?? '—'} / max ${nsuNfe.max_nsu ?? '—'}`,
      );
    }
    if (nsuCte) {
      linhasSefaz.push(
        `NSU CT-e: ${nsuCte.ultimo_nsu_inicial ?? '—'} → ${nsuCte.ultimo_nsu_final ?? nsuCte.ultimo_nsu ?? '—'} / max ${nsuCte.max_nsu ?? '—'}`,
      );
    }
    if (data.lotes_processados != null) {
      linhasSefaz.push(`Lotes processados: ${data.lotes_processados} (limite ${data.limite_lotes ?? limiteLotesCaptura})`);
    }

    const novosTotal = (r?.nfe_novas ?? 0) + (r?.cte_novos ?? 0);
    const dupTotal = (r?.nfe_duplicadas ?? 0) + (r?.cte_duplicados ?? 0);

    if (novosTotal === 0 && dupTotal === 0) {
      toast.message('Nenhum DF-e novo encontrado nesta captura.');
    } else if (data.sucesso) {
      toast.success(
        `Captura SEFAZ concluída. NF-e: ${r?.nfe_novas ?? 0} nova(s), ${r?.nfe_duplicadas ?? 0} duplicada(s). CT-e: ${r?.cte_novos ?? 0} novo(s), ${r?.cte_duplicados ?? 0} duplicado(s).`,
      );
    } else {
      toast.warning(
        `Captura SEFAZ parcial. NF-e: ${r?.nfe_novas ?? 0} nova(s). CT-e: ${r?.cte_novos ?? 0} novo(s).`,
      );
    }

    linhasSefaz.forEach((linha) => toast.message(linha));
    if (data.ainda_tem_nsu_pendente) {
      toast.warning(
        'A SEFAZ informou que ainda há documentos pendentes. Execute nova captura para continuar.',
      );
    }
    for (const msg of data.mensagens ?? []) {
      if (
        msg !== 'Nenhum DF-e novo encontrado nesta captura.' &&
        !msg.startsWith('Ainda existem documentos pendentes na SEFAZ')
      ) {
        toast.message(msg);
      }
    }
    for (const aviso of data.avisos ?? []) {
      toast.message(aviso);
    }
    for (const erro of data.erros ?? []) {
      toast.error(erro);
    }
  };

  const executarCapturaSefaz = async () => {
    if (!empresaId) {
      toast.error('Selecione a empresa ativa antes de capturar DF-e.');
      return;
    }
    setCapturando(true);
    setModalCapturaOpen(false);
    try {
      const data = await centralDfeService.capturarSefaz({
        empresa_id: empresaId,
        tipos: ['NFE', 'CTE'],
        modo: 'incremental',
        limite_lotes: limiteLotesCaptura,
      });
      exibirResumoCaptura(data);
      if (data.sefaz_consultada) {
        await reload();
      }
    } catch (err) {
      const msg = apiErrorMessage(err, {
        fallback: 'Não foi possível consultar a SEFAZ. Verifique certificado e conectividade.',
      });
      if (/certificado/i.test(msg)) {
        toast.error('Certificado digital não disponível/configurado para consulta DF-e.');
      } else {
        toast.error(msg);
      }
    } finally {
      setCapturando(false);
    }
  };

  return (
    <div className="erp-page">
      <PageHeader
        title="DF-e Recebidos"
        subtitle="NF-e de fornecedores e CT-e de transportadoras emitidos contra o CNPJ da empresa, pendentes de entrada ou tratamento."
        icon={Inbox}
        actions={
          <button
            type="button"
            className="erp-btn-primary inline-flex items-center gap-2"
            disabled={!empresaId || capturando}
            onClick={() => setModalCapturaOpen(true)}
          >
            {capturando ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Consultando SEFAZ…
              </>
            ) : (
              <>
                <CloudDownload className="h-4 w-4" aria-hidden />
                Capturar DF-e da SEFAZ
              </>
            )}
          </button>
        }
      />

      <p className="text-sm text-muted-foreground mb-4 -mt-2">
        Fila de documentos emitidos contra <strong>{empresaLabel}</strong>
        {empresaInfo?.cnpj ? ` (${fmtCnpj(empresaInfo.cnpj)})` : ''} sem entrada lançada no ERP.
        Use &quot;Incluir já tratados&quot; para ver conferidos, divergentes, ignorados ou já lançados.
      </p>

      {resumo && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <KpiCard label="Pendentes de entrada" value={resumo.pendentes_entrada} />
          <KpiCard label="NF-e fornecedores" value={resumo.nfe_fornecedores} />
          <KpiCard label="CT-e transportadoras" value={resumo.cte_transportadoras} />
          <KpiCard label="Divergentes" value={resumo.divergentes} />
          <KpiCard label="Ignorados" value={resumo.ignorados} />
          <KpiCard label="Já tratados" value={resumo.ja_tratados} />
        </div>
      )}

      <NexusCard className="p-4 mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="erp-label">Emissão de</label>
            <input
              type="date"
              className="erp-input mt-1"
              value={dataEmissaoInicio}
              onChange={(e) => {
                setCompetenciaEmissao('');
                setDataEmissaoInicio(e.target.value);
              }}
            />
          </div>
          <div>
            <label className="erp-label">Emissão até</label>
            <input
              type="date"
              className="erp-input mt-1"
              value={dataEmissaoFim}
              onChange={(e) => {
                setCompetenciaEmissao('');
                setDataEmissaoFim(e.target.value);
              }}
            />
          </div>
          <div>
            <label className="erp-label">Competência (mm/aaaa)</label>
            <div className="flex gap-2 mt-1">
              <input
                className="erp-input w-28"
                value={competenciaEmissao}
                onChange={(e) => setCompetenciaEmissao(e.target.value)}
                placeholder="06/2026"
              />
              <button type="button" className="erp-btn-outline erp-btn-sm" onClick={aplicarCompetencia}>
                Aplicar
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 items-end">
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => {
                const p = intervaloMesAtual();
                aplicarPeriodoEmissao(p.inicio, p.fim);
              }}
            >
              Este mês
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => {
                const p = intervaloMesAnterior();
                aplicarPeriodoEmissao(p.inicio, p.fim);
              }}
            >
              Mês anterior
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => aplicarPeriodoEmissao('2026-06-01', '2026-06-30')}
            >
              Jun/2026
            </button>
            <button type="button" className="erp-btn-ghost erp-btn-sm" onClick={limparPeriodoEmissao}>
              Limpar período
            </button>
          </div>
          <div className="min-w-[220px]">
            <label className="erp-label">Chave de acesso</label>
            <input
              className="erp-input mt-1 w-full font-mono text-sm"
              value={chaveFiltro}
              onChange={(e) => setChaveFiltro(e.target.value)}
              placeholder="44 dígitos"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="erp-label">Busca</label>
            <input
              className="erp-input mt-1 w-full"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Número, emitente, chave…"
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-3">
          Filtro ativo: {periodoFiltroLabel}. Padrão: somente pendentes/importados — use &quot;Incluir já tratados&quot; para conferidos, ignorados ou já lançados.
        </p>
        <FilterBar filters={filterDefs} onChange={setFilter} />
      </NexusCard>

      <DataTableShell>
        {loading && <TableSkeleton rows={8} />}
        {!loading && error && <ErrorState message={error} onRetry={() => void reload()} />}
        {!loading && !error && items.length === 0 && (
          <EmptyState
            title="Nenhum DF-e encontrado no filtro atual"
            description={
              dataEmissaoInicio || dataEmissaoFim || competenciaEmissao
                ? `Não há documentos de fornecedores ou transportadoras para ${periodoFiltroLabel}. Tente capturar da SEFAZ, ampliar o período ou marque "Incluir já tratados".`
                : 'Não há NF-e de fornecedores ou CT-e de transportadoras pendentes contra o CNPJ da empresa. Use os filtros de emissão ou capture da SEFAZ.'
            }
          />
        )}
        {!loading && !error && items.length > 0 && (
          <>
            <DataTable>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Documento</th>
                  <th>Emitente</th>
                  <th>CNPJ emitente</th>
                  <th>Emissão</th>
                  <th className="text-right">Valor</th>
                  <th>Status de entrada</th>
                  <th className="w-28">Ações</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={`${row.tipo_documento}-${row.id}`}>
                    <td>
                      <span className="text-sm font-medium">{row.tipo_label}</span>
                    </td>
                    <td>
                      <div className="text-sm font-medium">
                        {row.numero || '—'}
                        {row.serie ? ` / ${row.serie}` : ''}
                      </div>
                      <div className="text-xs text-muted-foreground font-mono" title={row.chave_acesso || undefined}>
                        {row.chave_resumida || chaveNfeResumida(row.chave_acesso)}
                      </div>
                    </td>
                    <td className="text-sm">{row.emitente_nome || '—'}</td>
                    <td className="text-sm font-mono">{fmtCnpj(row.emitente_cnpj)}</td>
                    <td className="text-sm whitespace-nowrap">{fmtData(row.data_emissao)}</td>
                    <td className="text-sm text-right tabular-nums">{fmtMoney(row.valor_total)}</td>
                    <td>
                      <StatusBadge status={statusEntradaBadge(row.status_entrada)} />
                      <div className="text-xs text-muted-foreground mt-1">{row.status_entrada_label}</div>
                    </td>
                    <td>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          className="erp-btn-ghost p-1.5"
                          title="Ver detalhe"
                          onClick={() => abrirDetalhe(row)}
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        {row.detalhe_rota && (
                          <Link
                            to={row.detalhe_rota}
                            className="erp-btn-ghost p-1.5 inline-flex"
                            title="Abrir tela de origem"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </Link>
                        )}
                        {row.chave_acesso && (
                          <button
                            type="button"
                            className="erp-btn-ghost p-1.5"
                            title={copiadoId === row.id ? 'Copiado!' : 'Copiar chave'}
                            onClick={() => void copiarChave(row)}
                          >
                            <Copy className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            <PaginationControls
              page={page}
              pageSize={pageSize}
              totalPages={totalPages}
              count={count}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          </>
        )}
      </DataTableShell>

      <CTeHistoricoDetalheModal
        cteId={detalheRow?.tipo_documento === 'CTE' ? detalheRow.id : null}
        open={modalCteOpen}
        onClose={() => setModalCteOpen(false)}
      />

      <AlertDialog open={modalCapturaOpen} onOpenChange={setModalCapturaOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Capturar DF-e da SEFAZ</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-sm text-muted-foreground">
                <p>
                  Esta ação consulta a SEFAZ com o certificado da empresa e importa para a fila DF-e
                  Recebidos documentos emitidos contra o CNPJ da Nexus. Busca NF-e de fornecedores e CT-e
                  de transportadoras em produção. Não gera entrada, financeiro ou estoque.
                </p>
                <div>
                  <label className="erp-label" htmlFor="limite-lotes-captura">
                    Lotes SEFAZ por execução
                  </label>
                  <select
                    id="limite-lotes-captura"
                    className="erp-input mt-1 w-full"
                    value={limiteLotesCaptura}
                    onChange={(e) => setLimiteLotesCaptura(Number(e.target.value))}
                    disabled={capturando}
                  >
                    <option value={3}>3 lotes (padrão)</option>
                    <option value={5}>5 lotes</option>
                    <option value={10}>10 lotes</option>
                  </select>
                  <p className="text-xs mt-1">
                    Chamadas excessivas podem gerar rejeição ou consumo indevido na SEFAZ. Se ainda houver NSU pendente, execute nova captura manualmente.
                  </p>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={capturando}>Cancelar</AlertDialogCancel>
            <AlertDialogAction disabled={capturando} onClick={() => void executarCapturaSefaz()}>
              Consultar SEFAZ
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default CentralDfe;
