import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp, FileCheck, Copy, ClipboardList, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import { empresasService } from '@/services/api/empresas';
import { fornecedoresService } from '@/services/api/fornecedores';
import {
  nfeHistoricaEntradaImportadaService,
  type NFeEntradaHistoricaDetalhe,
  type NFeEntradaHistoricaImportResultado,
  type NFeEntradaHistoricaList,
} from '@/services/api/nfeHistoricaEntradaImportada';
import type { Empresa, Fornecedor } from '@/types';
import {
  copiarTextoParaAreaDeTransferencia,
  montarTextoDiagnosticoNfeEntradaXml,
  normalizarFalhaImportacaoXml,
} from '@/utils/nfeXmlImportDiagnostico';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { PaginationControls } from '@/components/list/PaginationControls';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';
import { NFeEntradaReabrirModal } from '@/components/fiscal/NFeEntradaReabrirModal';
import { NexusCard } from '@/components/nexus/NexusCard';
import { NexusButton } from '@/components/nexus';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import { openBlobInNewTab } from '@/lib/downloadBlobFile';
import {
  aplicarCompetenciaMmAaaa,
  intervaloMesAnterior,
  intervaloMesAtual,
  labelPeriodoFiltro,
  PERIODO_ATALHO_JUN_2026,
} from '@/lib/periodoFiltroFiscal';
import {
  labelBotaoPrincipalConferenciaNfeEntradaHistorica,
  labelStatusOperacionalNfeEntradaHistorica,
  rotaConferenciaNfeEntradaHistorica,
  STATUS_CONFERENCIA_FILTRO_OPCOES,
  statusBadgeTokenNfeEntradaHistorica,
} from '@/lib/nfeEntradaHistoricaImportadaUi';

const TIPO_DATA_STORAGE_KEY = 'nfe_entrada_hist_tipo_data';

function lerTipoDataPersistido(): 'emissao' | 'entrada' {
  try {
    const stored = localStorage.getItem(TIPO_DATA_STORAGE_KEY);
    if (stored === 'entrada' || stored === 'emissao') return stored;
  } catch {
    /* ignore */
  }
  return 'emissao';
}

const NFeHistoricaEntradaImportada = () => {
  const navigate = useNavigate();
  const tipoDataInicial = lerTipoDataPersistido();
  const [tipoData, setTipoDataState] = useState<'emissao' | 'entrada'>(tipoDataInicial);
  const [competencia, setCompetencia] = useState('');
  const [chaveFiltro, setChaveFiltro] = useState('');
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
    error: loadError,
    reload,
  } = usePaginatedList<NFeEntradaHistoricaList>({
    fetchPage: nfeHistoricaEntradaImportadaService.listPaginated,
    initialFilters: tipoDataInicial === 'entrada' ? { tipo_data: 'entrada' } : {},
  });
  const empresaId = filters.empresa_destinataria_id || '';
  const fornecedorId = filters.fornecedor_id || '';
  const dataInicio = filters.data_inicio || '';
  const dataFim = filters.data_fim || '';
  const statusConferencia = filters.status_conferencia || '';

  const setTipoData = useCallback(
    (value: 'emissao' | 'entrada') => {
      setTipoDataState(value);
      try {
        localStorage.setItem(TIPO_DATA_STORAGE_KEY, value);
      } catch {
        /* ignore */
      }
      setFilter('tipo_data', value === 'emissao' ? '' : value);
    },
    [setFilter],
  );

  const aplicarPeriodo = useCallback(
    (inicio: string, fim: string) => {
      setCompetencia('');
      setFilters((prev) => {
        const next = { ...prev };
        if (inicio) next.data_inicio = inicio;
        else delete next.data_inicio;
        if (fim) next.data_fim = fim;
        else delete next.data_fim;
        return next;
      });
    },
    [setFilters],
  );

  const limparPeriodo = useCallback(() => {
    setCompetencia('');
    setFilters((prev) => {
      const next = { ...prev };
      delete next.data_inicio;
      delete next.data_fim;
      return next;
    });
  }, [setFilters]);

  const aplicarCompetencia = useCallback(() => {
    const periodo = aplicarCompetenciaMmAaaa(competencia);
    if (!periodo) {
      toast.error('Informe a competência no formato mm/aaaa.');
      return;
    }
    setFilters((prev) => ({
      ...prev,
      data_inicio: periodo.inicio,
      data_fim: periodo.fim,
    }));
  }, [competencia, setFilters]);

  const periodoFiltroLabel = useMemo(
    () => labelPeriodoFiltro({ dataInicio, dataFim, competencia }),
    [dataInicio, dataFim, competencia],
  );

  // Chave dedicada alimenta a busca textual (API já filtra por chave_acesso).
  useEffect(() => {
    const digits = chaveFiltro.replace(/\D/g, '');
    if (!digits) return;
    setSearch(digits);
  }, [chaveFiltro, setSearch]);

  const [busy, setBusy] = useState(false);
  const [resultado, setResultado] = useState<NFeEntradaHistoricaImportResultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [detalhe, setDetalhe] = useState<NFeEntradaHistoricaDetalhe | null>(null);
  const [modal, setModal] = useState(false);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [diagCopiado, setDiagCopiado] = useState(false);
  const [reabrirId, setReabrirId] = useState<number | null>(null);

  useEffect(() => {
    void (async () => {
      const [e, f] = await Promise.all([empresasService.getAll(), fornecedoresService.getAll()]);
      setEmpresas(e);
      setFornecedores(f);
    })().catch((e) => setErro(apiErrorMessage(e)));
  }, []);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setErro(null);
    setBusy(true);
    try {
      const res = await nfeHistoricaEntradaImportadaService.importarXmls(Array.from(files));
      setResultado(res);
      void reload();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const falhasEntrada = resultado?.erros?.length
    ? resultado.erros.map((raw) => normalizarFalhaImportacaoXml(raw))
    : [];

  const copiarDiagnosticoEntrada = async () => {
    if (!resultado) return;
    await copiarTextoParaAreaDeTransferencia(montarTextoDiagnosticoNfeEntradaXml(resultado));
    setDiagCopiado(true);
    window.setTimeout(() => setDiagCopiado(false), 2500);
  };

  const imprimirDanfe = async (row: NFeEntradaHistoricaList) => {
    try {
      const blob = await nfeHistoricaEntradaImportadaService.danfeBlob(row.id);
      openBlobInNewTab(blob, `DANFE_NFe_Entrada_${row.id}.pdf`);
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível gerar o DANFE.' }));
    }
  };

  return (
    <div>
      <PageHeader
        title="Base de NF-e Entrada Importada"
        description="XMLs de entrada usados para apuração fiscal, base contábil, relatórios e precificação. Não geram estoque, contas a pagar ou conciliação operacional automaticamente."
      />

      <NexusCard variant="action" className="mb-6">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="flex-1">
            <h2 className="nexus-heading-md flex items-center gap-2">
              <FileUp className="h-5 w-5" />
              Importar XMLs de NF-e de entrada
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Alimenta apuração, contábil, BI e precificação. Sem efeito operacional automático (estoque, financeiro, pedido).
            </p>
          </div>
          <NexusButton asChild disabled={busy}>
            <label className="cursor-pointer shrink-0">
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
          </NexusButton>
        </div>
        {erro ? <p className="text-sm text-destructive mt-3">{erro}</p> : null}
      </NexusCard>

      {resultado && (
        <div className="erp-card p-4 mb-4 space-y-4">
          <div className="flex flex-wrap justify-between gap-2 items-start">
            <div className="grid md:grid-cols-3 gap-3 flex-1">
              <div>
                <div className="text-xs text-muted-foreground">Importadas</div>
                <div className="text-xl font-semibold">{resultado.resumo.importadas}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Duplicadas</div>
                <div className="text-xl font-semibold">{resultado.resumo.duplicadas}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Falhas</div>
                <div className="text-xl font-semibold">{resultado.resumo.erros}</div>
              </div>
            </div>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1 shrink-0"
              onClick={() => void copiarDiagnosticoEntrada()}
            >
              <ClipboardList className="h-4 w-4" />
              {diagCopiado ? 'Copiado!' : 'Copiar diagnóstico'}
            </button>
          </div>
          {resultado.importadas.slice(0, 5).map((r) => (
            <div key={r.id} className="text-xs text-muted-foreground">
              <FileCheck className="inline h-3 w-3 mr-1 text-success" />
              {r.arquivo}
            </div>
          ))}
          {resultado.duplicadas.slice(0, 5).map((r) => (
            <div key={`${r.arquivo}-${r.chave_acesso}`} className="text-xs text-muted-foreground">
              <Copy className="inline h-3 w-3 mr-1" />
              {r.arquivo}
            </div>
          ))}
          {falhasEntrada.length > 0 && (
            <div className="overflow-x-auto border border-border rounded-md max-h-80 overflow-y-auto">
              <table className="erp-table text-xs">
                <thead>
                  <tr>
                    <th>Arquivo</th>
                    <th>Chave</th>
                    <th>Tipo doc.</th>
                    <th>Tipo erro</th>
                    <th>Mensagem</th>
                    <th>Ação sugerida</th>
                  </tr>
                </thead>
                <tbody>
                  {falhasEntrada.map((row, idx) => (
                    <tr key={`${row.arquivo}-${idx}`}>
                      <td className="font-mono max-w-[120px] truncate" title={row.arquivo}>
                        {row.arquivo}
                      </td>
                      <td className="font-mono whitespace-nowrap">{row.chave || '—'}</td>
                      <td>{row.tipoDocumento}</td>
                      <td>{row.tipoErro}</td>
                      <td className="max-w-md whitespace-pre-wrap break-words">{row.mensagemCompleta}</td>
                      <td className="max-w-xs text-muted-foreground">{row.acaoSugerida}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <NexusCard className="p-4 mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="erp-label">{tipoData === 'entrada' ? 'Entrada de' : 'Emissão de'}</label>
            <input
              type="date"
              className="erp-input mt-1"
              value={dataInicio}
              onChange={(e) => {
                setCompetencia('');
                setFilter('data_inicio', e.target.value);
              }}
            />
          </div>
          <div>
            <label className="erp-label">{tipoData === 'entrada' ? 'Entrada até' : 'Emissão até'}</label>
            <input
              type="date"
              className="erp-input mt-1"
              value={dataFim}
              onChange={(e) => {
                setCompetencia('');
                setFilter('data_fim', e.target.value);
              }}
            />
          </div>
          <div>
            <label className="erp-label">Competência (mm/aaaa)</label>
            <div className="flex gap-2 mt-1">
              <input
                className="erp-input w-28"
                value={competencia}
                onChange={(e) => setCompetencia(e.target.value)}
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
                aplicarPeriodo(p.inicio, p.fim);
              }}
            >
              Este mês
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => {
                const p = intervaloMesAnterior();
                aplicarPeriodo(p.inicio, p.fim);
              }}
            >
              Mês anterior
            </button>
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              onClick={() => aplicarPeriodo(PERIODO_ATALHO_JUN_2026.inicio, PERIODO_ATALHO_JUN_2026.fim)}
            >
              Jun/2026
            </button>
            <button type="button" className="erp-btn-ghost erp-btn-sm" onClick={limparPeriodo}>
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
              onChange={(e) => {
                setChaveFiltro('');
                setSearch(e.target.value);
              }}
              placeholder="Número, fornecedor, chave…"
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground mt-3">
          Filtro ativo: {periodoFiltroLabel}
          {tipoData === 'entrada' ? ' (por data de entrada na conferência)' : ' (por data de emissão)'}.
        </p>
        <div className="flex flex-wrap gap-3 items-end mt-3 pt-3 border-t border-border/60">
          <select className="erp-select" value={empresaId} onChange={(e) => setFilter('empresa_destinataria_id', e.target.value)}>
            <option value="">Empresa destinatária (todas)</option>
            {empresas.map((e) => (
              <option key={e.id} value={e.id}>
                {e.razao_social}
              </option>
            ))}
          </select>
          <select className="erp-select" value={fornecedorId} onChange={(e) => setFilter('fornecedor_id', e.target.value)}>
            <option value="">Fornecedor emitente (todos)</option>
            {fornecedores.map((f) => (
              <option key={f.id} value={f.id}>
                {f.razao_social}
              </option>
            ))}
          </select>
          <select
            className="erp-select"
            value={statusConferencia}
            onChange={(e) => setFilter('status_conferencia', e.target.value)}
          >
            {STATUS_CONFERENCIA_FILTRO_OPCOES.map((opt) => (
              <option key={opt.value || 'todos'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            className="erp-select"
            value={tipoData}
            onChange={(e) => setTipoData(e.target.value === 'entrada' ? 'entrada' : 'emissao')}
            title="Tipo de data para o filtro de período"
          >
            <option value="emissao">Data de emissão</option>
            <option value="entrada">Data de entrada</option>
          </select>
          <NexusButton type="button" variant="outline" onClick={() => void reload()}>
            Atualizar
          </NexusButton>
        </div>
      </NexusCard>

      {loadError ? <ErrorState onRetry={() => void reload()} /> : null}
      {loading ? <TableSkeleton rows={6} cols={7} /> : null}
      {!loading && !loadError ? (
        <DataTableShell>
        <DataTable>
          <thead>
            <tr>
              <th>Chave</th>
              <th>Fornecedor</th>
              <th>Número</th>
              <th>Emissão</th>
              <th>Importado em</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <EmptyState message="Nenhuma NF-e de entrada importada encontrada para os filtros atuais." />
                </td>
              </tr>
            ) : (
            items.map((r) => (
              <tr key={r.id}>
                <td className="font-mono text-xs" title={r.chave_acesso}>{chaveNfeResumida(r.chave_acesso)}</td>
                <td>{r.fornecedor_nome || '—'}</td>
                <td>{r.numero}/{r.serie}</td>
                <td>{r.dh_emissao?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
                <td>{r.importado_em?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
                <td>
                  <div className="flex flex-col gap-1">
                    <StatusBadge
                      status={statusBadgeTokenNfeEntradaHistorica(r)}
                      label={labelStatusOperacionalNfeEntradaHistorica(r)}
                    />
                    <DfeClassificacaoBadges classificacao={r.classificacao_dfe} max={3} />
                  </div>
                </td>
                <td>
                  <div className="flex flex-wrap gap-2">
                    <NexusButton
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void nfeHistoricaEntradaImportadaService.getById(r.id).then((d) => { setDetalhe(d); setModal(true); }).catch((e) => setErro(apiErrorMessage(e)));
                      }}
                    >
                      Detalhes
                    </NexusButton>
                    {r.tem_xml_conteudo ? (
                      <NexusButton
                        type="button"
                        variant="outline"
                        size="sm"
                        title="Imprimir DANFE"
                        aria-label="Imprimir DANFE"
                        onClick={() => void imprimirDanfe(r)}
                      >
                        <Printer className="h-4 w-4" />
                      </NexusButton>
                    ) : null}
                    <NexusButton
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(rotaConferenciaNfeEntradaHistorica(r.id, r))}
                    >
                      {labelBotaoPrincipalConferenciaNfeEntradaHistorica(r)}
                    </NexusButton>
                    <NexusButton
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setReabrirId(r.id)}
                    >
                      Reabrir entrada para correção
                    </NexusButton>
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

      <Modal isOpen={modal} onClose={() => setModal(false)} title="NF-e de entrada importada (histórico)" size="xl">
        {detalhe && (
          <div className="space-y-3 text-sm">
            <p><strong>Chave:</strong> {detalhe.chave_acesso}</p>
            <p><strong>Empresa (ERP):</strong> {detalhe.empresa_nome || '—'} {detalhe.papel_empresa ? `(${detalhe.papel_empresa})` : ''}</p>
            <p><strong>Fornecedor:</strong> {detalhe.fornecedor_nome || '—'}</p>
            <p><strong>Status XML:</strong> {detalhe.cstat || '—'} {detalhe.xmotivo ? `- ${detalhe.xmotivo}` : ''}</p>
            <NexusButton type="button" variant="outline" size="sm" onClick={() => setReabrirId(detalhe.id)}>
              Reabrir entrada para correção
            </NexusButton>
          </div>
        )}
      </Modal>
      <NFeEntradaReabrirModal
        open={reabrirId !== null}
        nfeHistoricaId={reabrirId}
        onOpenChange={(open) => {
          if (!open) setReabrirId(null);
        }}
        onSuccess={(resultado) => {
          toast.success(resultado.mensagem);
          setModal(false);
          void reload();
          navigate(`/nfe-entrada/${resultado.conferencia.nf_entrada_historica}/conferencia`);
        }}
      />
    </div>
  );
};

export default NFeHistoricaEntradaImportada;

