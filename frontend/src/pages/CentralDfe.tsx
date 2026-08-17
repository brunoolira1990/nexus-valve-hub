import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Copy, ExternalLink, Eye, FileDown, Inbox, Loader2, MoreVertical, Printer, RefreshCw, Stamp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { CTeHistoricoDetalheModal } from '@/components/fiscal/CTeHistoricoDetalheModal';
import { CentralDfeCteDetalheModal } from '@/components/fiscal/CentralDfeCteDetalheModal';
import { CentralDfeWorkspaceSheet } from '@/components/fiscal/CentralDfeWorkspaceSheet';
import { ManifestacaoDestinatarioModals } from '@/components/fiscal/ManifestacaoDestinatarioModals';
import { FilterBar } from '@/components/list/FilterBar';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { PaginationControls } from '@/components/list/PaginationControls';
import { PageHeader } from '@/components/PageHeader';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { NexusCard } from '@/components/nexus/NexusCard';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { TableSkeleton } from '@/components/nexus/Skeleton';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAppContexto } from '@/hooks/useAppContexto';
import { useManifestacaoDestinatario } from '@/hooks/useManifestacaoDestinatario';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import {
  isNfeFornecedorAplicavel,
  podeArmazenarXmlNfe,
  podeManifestarNfe,
  statusManifestacaoExibicao,
  statusXmlExibicao,
  xmlJaArmazenado,
} from '@/lib/manifestacaoDestinatarioUi';
import {
  documentoCentralMatchBusca,
  isCteTransportadora,
  labelAbrirBaseImportada,
  labelStatusXmlManifestacao,
  LABEL_ARMAZENAR_XML_CTE,
  LABEL_BAIXAR_XML,
  LABEL_CONFERIR_CTE,
  LABEL_IMPORTAR_XML_CTE,
  LABEL_IMPORTAR_XML_NFE,
  LABEL_IMPRIMIR_DACTE,
  LABEL_IMPRIMIR_DANFE,
  LABEL_VER_CTE,
  podeAbrirBaseImportada,
  podeArmazenarXmlCte,
  rotaAbrirBaseImportada,
  statusManifestacaoCteExibicao,
  statusXmlCteExibicao,
  tooltipAbrirBaseImportada,
  TOOLTIP_ARMAZENAR_XML_CTE,
  TOOLTIP_BAIXAR_XML,
  TOOLTIP_CONFERIR_CTE,
  TOOLTIP_IMPORTAR_XML_CTE,
  TOOLTIP_IMPORTAR_XML_NFE,
  TOOLTIP_IMPRIMIR_DACTE,
  TOOLTIP_IMPRIMIR_DANFE,
  TOOLTIP_VER_CTE,
} from '@/lib/centralDfeUi';
import {
  ESTADOS_INBOX_FILTRO,
  badgeStatusEstadoConsolidado,
  resolverEstadoConsolidadoExibicao,
  textosAlertaEstadoConsolidado,
} from '@/lib/inboxFiscalUi';
import { nfeHistoricaEntradaImportadaService } from '@/services/api/nfeHistoricaEntradaImportada';
import { cteHistoricoImportadoService } from '@/services/api/cteHistoricoImportado';
import {
  extrairSerieNumeroDaChaveDfe,
  formatNumeroSerieInbox,
  resolverNumeroSerieInbox,
} from '@/lib/chaveDfeDocumento';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import { openBlobInNewTab } from '@/lib/downloadBlobFile';
import { labelStatusEntradaNfeConferenciaFinalizada } from '@/lib/conferenciaNfeLabels';
import {
  centralDfeService,
  type CentralDfeDocumento,
  type CentralDfeListResponse,
  type CentralDfeResumo,
} from '@/services/api/centralDfe';
import { apiErrorMessage } from '@/services/api/config';
import type { NFeDestinadaDocumento } from '@/services/api/manifestacaoDestinatario';
import { copiarTextoParaAreaDeTransferencia } from '@/utils/nfeXmlImportDiagnostico';
import {formatMoneyBRL} from '@/lib/numberFields';

const fmtMoney = (v: string | number | null | undefined): string => {
  const n = Number(String(v ?? '0').replace(',', '.'));
  return `formatMoneyBRL(n)`;
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

/** XML + Ações fixas à direita — sempre visíveis com scroll horizontal nas demais colunas. */
const CLASSE_COLUNA_MANIFEST_TH = 'min-w-[7.5rem] w-[7.5rem] whitespace-nowrap';
const CLASSE_COLUNA_MANIFEST_TD = 'min-w-[7.5rem] w-[7.5rem] whitespace-nowrap align-middle';
const CLASSE_COLUNA_XML_TH =
  'sticky right-[6rem] z-10 min-w-[8rem] w-[8rem] whitespace-nowrap bg-muted/95 shadow-[-2px_0_4px_-2px_hsl(var(--border))]';
const CLASSE_COLUNA_XML_TD =
  'sticky right-[6rem] z-10 min-w-[8rem] w-[8rem] whitespace-nowrap bg-card shadow-[-2px_0_4px_-2px_hsl(var(--border))] group-hover:bg-muted/50';
const CLASSE_COLUNA_ACOES_TH =
  'sticky right-0 z-20 min-w-[6rem] w-[6rem] whitespace-nowrap bg-muted/95 text-right shadow-[-4px_0_6px_-2px_hsl(var(--border))]';
const CLASSE_COLUNA_ACOES_TD =
  'sticky right-0 z-20 min-w-[6rem] w-[6rem] whitespace-nowrap bg-card text-right align-middle shadow-[-4px_0_6px_-2px_hsl(var(--border))] group-hover:bg-muted/50';
const CLASSE_BADGE_COLUNA_INBOX = 'whitespace-nowrap shrink-0 max-w-none';

type CentralDfeAcoesLinhaProps = {
  row: CentralDfeDocumento;
  manifestacao: NFeDestinadaDocumento | null;
  somenteResumo: boolean;
  loadingAcaoManual: boolean;
  copiadoId: number | null;
  exibirManifestar: boolean;
  exibirArmazenarXml: boolean;
  exibirBaixarXml: boolean;
  exibirImprimirPdf: boolean;
  exibirAbrirBaseImportada: boolean;
  onAbrirDetalhe: () => void;
  onManifestar: () => void;
  onArmazenarXmlNfe: () => void;
  onBaixarXml: () => void;
  onImprimirPdf: () => void;
  onAbrirDetalheCte: () => void;
  onArmazenarXmlCte: () => void;
  onConferirCte: () => void;
  onCopiarChave: () => void;
};

function CentralDfeAcoesLinha({
  row,
  manifestacao,
  somenteResumo,
  loadingAcaoManual,
  copiadoId,
  exibirManifestar,
  exibirArmazenarXml,
  exibirBaixarXml,
  exibirImprimirPdf,
  exibirAbrirBaseImportada,
  onAbrirDetalhe,
  onManifestar,
  onArmazenarXmlNfe,
  onBaixarXml,
  onImprimirPdf,
  onAbrirDetalheCte,
  onArmazenarXmlCte,
  onConferirCte,
  onCopiarChave,
}: CentralDfeAcoesLinhaProps) {
  const navigate = useNavigate();
  const cte = isCteTransportadora(row);
  const nfe = isNfeFornecedorAplicavel(row);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="erp-btn-ghost erp-btn-sm inline-flex items-center gap-1 text-xs font-medium"
          aria-label="Ações do documento"
        >
          Ações
          <MoreVertical className="h-3.5 w-3.5 shrink-0 opacity-70" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56" onOpenAutoFocus={(ev) => ev.preventDefault()}>
        {nfe && (
          <>
            <DropdownMenuItem className="cursor-pointer" onSelect={onAbrirDetalhe}>
              <span className="flex items-center gap-2">
                <Eye className="h-4 w-4 shrink-0" />
                Ver detalhe
              </span>
            </DropdownMenuItem>
            {exibirManifestar && (
              <DropdownMenuItem
                className="cursor-pointer"
                disabled={loadingAcaoManual}
                onSelect={onManifestar}
              >
                <span className="flex items-center gap-2">
                  <Stamp className="h-4 w-4 shrink-0" />
                  Manifestar
                </span>
              </DropdownMenuItem>
            )}
            {exibirArmazenarXml && (
              <DropdownMenuItem
                className="cursor-pointer"
                disabled={loadingAcaoManual}
                title={TOOLTIP_IMPORTAR_XML_NFE}
                onSelect={onArmazenarXmlNfe}
              >
                <span className="flex items-center gap-2">
                  <FileDown className="h-4 w-4 shrink-0" />
                  {LABEL_IMPORTAR_XML_NFE}
                </span>
              </DropdownMenuItem>
            )}
            {exibirBaixarXml && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={TOOLTIP_BAIXAR_XML}
                onSelect={onBaixarXml}
              >
                <span className="flex items-center gap-2">
                  <FileDown className="h-4 w-4 shrink-0" />
                  {LABEL_BAIXAR_XML}
                </span>
              </DropdownMenuItem>
            )}
            {exibirImprimirPdf && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={TOOLTIP_IMPRIMIR_DANFE}
                onSelect={onImprimirPdf}
              >
                <span className="flex items-center gap-2">
                  <Printer className="h-4 w-4 shrink-0" />
                  {LABEL_IMPRIMIR_DANFE}
                </span>
              </DropdownMenuItem>
            )}
            {exibirAbrirBaseImportada && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={tooltipAbrirBaseImportada(row)}
                onSelect={() => navigate(rotaAbrirBaseImportada(row))}
              >
                <span className="flex items-center gap-2">
                  <ExternalLink className="h-4 w-4 shrink-0" />
                  {labelAbrirBaseImportada(row)}
                </span>
              </DropdownMenuItem>
            )}
            {manifestacao && (
              <DropdownMenuItem className="cursor-pointer" onSelect={onAbrirDetalhe}>
                <span className="flex items-center gap-2">
                  <Eye className="h-4 w-4 shrink-0" />
                  Histórico
                </span>
              </DropdownMenuItem>
            )}
            {row.detalhe_rota && !somenteResumo && !exibirAbrirBaseImportada && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={tooltipAbrirBaseImportada(row)}
                onSelect={() => navigate(row.detalhe_rota)}
              >
                <span className="flex items-center gap-2">
                  <ExternalLink className="h-4 w-4 shrink-0" />
                  Abrir registro
                </span>
              </DropdownMenuItem>
            )}
          </>
        )}
        {cte && (
          <>
            <DropdownMenuItem className="cursor-pointer" onSelect={onAbrirDetalheCte}>
              <span className="flex items-center gap-2" title={TOOLTIP_VER_CTE}>
                {LABEL_VER_CTE}
              </span>
            </DropdownMenuItem>
            {podeArmazenarXmlCte(row) && (
              <DropdownMenuItem
                className="cursor-pointer"
                disabled={loadingAcaoManual}
                title={TOOLTIP_IMPORTAR_XML_CTE}
                onSelect={onArmazenarXmlCte}
              >
                <span className="flex items-center gap-2">
                  <FileDown className="h-4 w-4 shrink-0" />
                  {LABEL_IMPORTAR_XML_CTE}
                </span>
              </DropdownMenuItem>
            )}
            {exibirBaixarXml && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={TOOLTIP_BAIXAR_XML}
                onSelect={onBaixarXml}
              >
                <span className="flex items-center gap-2">
                  <FileDown className="h-4 w-4 shrink-0" />
                  {LABEL_BAIXAR_XML}
                </span>
              </DropdownMenuItem>
            )}
            {exibirImprimirPdf && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={TOOLTIP_IMPRIMIR_DACTE}
                onSelect={onImprimirPdf}
              >
                <span className="flex items-center gap-2">
                  <Printer className="h-4 w-4 shrink-0" />
                  {LABEL_IMPRIMIR_DACTE}
                </span>
              </DropdownMenuItem>
            )}
            {exibirAbrirBaseImportada && podeAbrirBaseImportada(row) && (
              <DropdownMenuItem
                className="cursor-pointer"
                title={tooltipAbrirBaseImportada(row)}
                onSelect={() => navigate(rotaAbrirBaseImportada(row))}
              >
                <span className="flex items-center gap-2">
                  <ExternalLink className="h-4 w-4 shrink-0" />
                  {labelAbrirBaseImportada(row)}
                </span>
              </DropdownMenuItem>
            )}
            <DropdownMenuItem
              className="cursor-pointer"
              title={TOOLTIP_CONFERIR_CTE}
              onSelect={onConferirCte}
            >
              <span className="flex items-center gap-2">{LABEL_CONFERIR_CTE}</span>
            </DropdownMenuItem>
          </>
        )}
        {row.chave_acesso && (
          <>
            {(nfe || cte) && <DropdownMenuSeparator />}
            <DropdownMenuItem className="cursor-pointer" onSelect={onCopiarChave}>
              <span className="flex items-center gap-2">
                <Copy className="h-4 w-4 shrink-0" />
                {copiadoId === row.id ? 'Chave copiada!' : 'Copiar chave'}
              </span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
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

const SYNC_MIN_INTERVAL_MS = 5 * 60 * 1000;
const SYNC_LOTES_PADRAO = 3;
const SYNC_LOTES_MANUAL = 8;

function fmtDateTime(d: Date): string {
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function lerUltimaSincronizacao(empresaId: number | undefined): Date | null {
  if (!empresaId) return null;
  const raw = sessionStorage.getItem(`central-dfe-sync-${empresaId}`);
  if (!raw) return null;
  const ts = Number(raw);
  return Number.isFinite(ts) ? new Date(ts) : null;
}

function registrarSincronizacao(empresaId: number): Date {
  const now = new Date();
  sessionStorage.setItem(`central-dfe-sync-${empresaId}`, String(now.getTime()));
  return now;
}

function podeSincronizarAutomaticamente(empresaId: number | undefined): boolean {
  if (!empresaId) return false;
  const raw = sessionStorage.getItem(`central-dfe-sync-${empresaId}`);
  if (!raw) return true;
  const ts = Number(raw);
  if (!Number.isFinite(ts)) return true;
  return Date.now() - ts >= SYNC_MIN_INTERVAL_MS;
}

function filtersShallowEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    if (a[key] !== b[key]) return false;
  }
  return true;
}

function mesclarLinhaCentral(
  row: CentralDfeDocumento,
  reconciliada: CentralDfeDocumento | undefined,
): CentralDfeDocumento {
  if (!reconciliada) return row;
  return {
    ...row,
    ...reconciliada,
    id: reconciliada.id,
    chave_acesso: reconciliada.chave_acesso || row.chave_acesso,
  };
}

function resumoParaLinhaCentral(m: NFeDestinadaDocumento): CentralDfeDocumento {
  const xmlArmazenado = m.status_xml === 'BAIXADO' && Boolean(m.nf_entrada_historica_id);
  const nfHistoricaId = m.nf_entrada_historica_id;
  const ext = extrairSerieNumeroDaChaveDfe(m.chave_acesso);
  return {
    id: xmlArmazenado && nfHistoricaId ? nfHistoricaId : m.id,
    tipo_documento: 'NFE_ENTRADA',
    chave_resumida: m.chave_resumida,
    chave_acesso: m.chave_acesso,
    numero: ext?.numero ?? '—',
    serie: ext?.serie ?? '',
    numero_via_chave: Boolean(ext),
    data_emissao: m.dh_emissao,
    data_importacao: null,
    emitente_nome: m.razao_social_emitente,
    emitente_cnpj: m.cnpj_emitente,
    uf: '',
    valor_total: m.valor_nf,
    status_entrada: 'IMPORTADO_BASE',
    status_entrada_label: xmlArmazenado ? 'Base NF-e Entrada Importada' : 'Resumo DF-e — pendente XML',
    tipo_label: 'NF-e Fornecedor',
    detalhe_rota: xmlArmazenado ? '/nfe-entrada-historica-importada' : '',
    empresa_id: m.empresa_id,
    xml_status: xmlArmazenado ? 'ARMAZENADO' : m.status_xml === 'DISPONIVEL' ? 'DISPONIVEL' : m.status_xml === 'ERRO' ? 'ERRO' : 'PENDENTE',
    xml_status_label: labelStatusXmlManifestacao(xmlArmazenado ? 'BAIXADO' : m.status_xml),
    xml_armazenado: xmlArmazenado,
    manifestacao_aplicavel: true,
  };
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
  const [copiadoId, setCopiadoId] = useState<number | null>(null);
  const [cteDetalheLocalRow, setCteDetalheLocalRow] = useState<CentralDfeDocumento | null>(null);
  const [modalCteDetalheLocalOpen, setModalCteDetalheLocalOpen] = useState(false);
  const [cteConferenciaRow, setCteConferenciaRow] = useState<CentralDfeDocumento | null>(null);
  const [modalCteConferenciaOpen, setModalCteConferenciaOpen] = useState(false);
  const [atualizandoDfe, setAtualizandoDfe] = useState(false);
  const [ultimaAtualizacao, setUltimaAtualizacao] = useState<Date | null>(null);
  const [erroAtualizacao, setErroAtualizacao] = useState<string | null>(null);
  const [avisoAtualizacao, setAvisoAtualizacao] = useState<string | null>(null);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [workspaceCtx, setWorkspaceCtx] = useState<{
    row: CentralDfeDocumento;
    manifestacao: NFeDestinadaDocumento | null;
    somenteResumo: boolean;
  } | null>(null);
  const syncEmAndamento = useRef(false);
  const chavesCentralNfeRef = useRef<Set<string>>(new Set());
  const recarregarTudoRef = useRef<() => Promise<void>>(async () => {});

  const periodoManifestacao = useMemo(() => {
    if (dataEmissaoInicio && dataEmissaoFim) {
      return { inicio: dataEmissaoInicio, fim: dataEmissaoFim };
    }
    return { inicio: '', fim: '' };
  }, [dataEmissaoInicio, dataEmissaoFim]);

  const {
    manifestacaoMap,
    manifestacaoSomenteResumo,
    documentosCentralPorChave,
    fechamento,
    detalhe,
    setDetalhe,
    manifestRow,
    setManifestRow,
    manifestModalKey,
    abrirModalManifestacao,
    confirmBaixar,
    setConfirmBaixar,
    confirmArmazenar,
    setConfirmArmazenar,
    confirmArmazenarCte,
    setConfirmArmazenarCte,
    dfeDetalheRow,
    setDfeDetalheRow,
    loadingAcaoManual,
    carregarManifestacao,
    abrirDetalheManifestacao,
    abrirDetalheDfeNfe,
    prepararManifestacaoPorDfe,
    iniciarManifestacaoManual,
    iniciarArmazenarXmlManual,
    sincronizarResumosDestinados,
    executarManifestacao,
    executarArmazenarXmlNfe,
    executarArmazenarXmlCte,
  } = useManifestacaoDestinatario(empresaId, periodoManifestacao);

  useEffect(() => {
    setUltimaAtualizacao(lerUltimaSincronizacao(empresaId));
  }, [empresaId]);

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
    debouncedSearch,
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

  const chavesCentralNfe = useMemo(
    () =>
      new Set(
        items
          .filter((row) => row.tipo_documento === 'NFE_ENTRADA' && row.chave_acesso)
          .map((row) => row.chave_acesso),
      ),
    [items],
  );

  const chavesCentralNfeKey = useMemo(
    () => [...chavesCentralNfe].sort().join('|'),
    [chavesCentralNfe],
  );

  const linhasExibidas = useMemo(() => {
    const chavesPagina = new Set(
      items.filter((row) => row.chave_acesso).map((row) => row.chave_acesso),
    );
    for (const [chave, doc] of documentosCentralPorChave) {
      if (doc.xml_armazenado) chavesPagina.add(chave);
    }
    const central = items.map((row) => {
      const reconciliada = row.chave_acesso
        ? documentosCentralPorChave.get(row.chave_acesso)
        : undefined;
      const merged = mesclarLinhaCentral(row, reconciliada);
      return {
        row: merged,
        manifestacao:
          merged.tipo_documento === 'NFE_ENTRADA'
            ? manifestacaoMap.get(merged.chave_acesso) ?? null
            : null,
        somenteResumo: false,
      };
    });
    const extrasReconciliados = [...documentosCentralPorChave.entries()]
      .filter(([chave, doc]) => doc.xml_armazenado && !items.some((row) => row.chave_acesso === chave))
      .map(([, doc]) => ({
        row: doc,
        manifestacao: manifestacaoMap.get(doc.chave_acesso) ?? null,
        somenteResumo: false,
      }));
    const extras = manifestacaoSomenteResumo
      .filter((m) => !chavesPagina.has(m.chave_acesso))
      .filter((m) => {
        const reconciliada = documentosCentralPorChave.get(m.chave_acesso);
        return !reconciliada?.xml_armazenado;
      })
      .map((m) => {
        const reconciliada = documentosCentralPorChave.get(m.chave_acesso);
        const row = reconciliada?.xml_armazenado
          ? reconciliada
          : resumoParaLinhaCentral(m);
        return {
          row,
          manifestacao: m,
          somenteResumo: !reconciliada?.xml_armazenado,
        };
      });
    return [...central, ...extrasReconciliados, ...extras]
      .sort((a, b) => {
        const da = a.row.data_emissao || '';
        const db = b.row.data_emissao || '';
        return db.localeCompare(da);
      })
      .filter(({ row }) => documentoCentralMatchBusca(row, debouncedSearch));
  }, [items, manifestacaoMap, manifestacaoSomenteResumo, documentosCentralPorChave, debouncedSearch]);

  useEffect(() => {
    void carregarManifestacao(chavesCentralNfe);
  }, [carregarManifestacao, chavesCentralNfeKey]);

  const recarregarTudo = useCallback(async () => {
    const response = await reload();
    const chaves = new Set(
      (response?.results ?? [])
        .filter((row) => row.tipo_documento === 'NFE_ENTRADA' && row.chave_acesso)
        .map((row) => row.chave_acesso),
    );
    await carregarManifestacao(chaves);
    setWorkspaceCtx((prev) => {
      if (!prev?.row.chave_acesso) return prev;
      const updated = (response?.results ?? []).find((r) => r.chave_acesso === prev.row.chave_acesso);
      if (!updated) return prev;
      const reconciliada = documentosCentralPorChave.get(prev.row.chave_acesso);
      return { ...prev, row: mesclarLinhaCentral(updated, reconciliada) };
    });
    return response;
  }, [reload, carregarManifestacao, documentosCentralPorChave]);

  const abrirWorkspace = (
    row: CentralDfeDocumento,
    manifestacao: NFeDestinadaDocumento | null,
    somenteResumo: boolean,
  ) => {
    setWorkspaceCtx({ row, manifestacao, somenteResumo });
    setWorkspaceOpen(true);
  };

  const fecharWorkspace = () => {
    setWorkspaceOpen(false);
    setWorkspaceCtx(null);
  };

  useEffect(() => {
    chavesCentralNfeRef.current = chavesCentralNfe;
  }, [chavesCentralNfe]);

  useEffect(() => {
    recarregarTudoRef.current = recarregarTudo;
  }, [recarregarTudo]);

  const sincronizarDfe = useCallback(
    async (manual = false) => {
      if (!empresaId || syncEmAndamento.current) return;
      if (!manual && !podeSincronizarAutomaticamente(empresaId)) {
        setUltimaAtualizacao(lerUltimaSincronizacao(empresaId));
        return;
      }

      syncEmAndamento.current = true;
      setAtualizandoDfe(true);
      setErroAtualizacao(null);
      setAvisoAtualizacao(null);

      let erroMsg: string | null = null;
      let avisoMsg: string | null = null;
      let syncComSucesso = false;

      try {
        // Sync automático permitido: captura DF-e + consulta resumos destinados (sem manifestar/baixar XML).
        try {
          const captura = await centralDfeService.capturarSefaz({
            empresa_id: empresaId,
            tipos: ['NFE', 'CTE'],
            modo: 'incremental',
            limite_lotes: manual ? SYNC_LOTES_MANUAL : SYNC_LOTES_PADRAO,
          });
          if (captura.sefaz_consultada) {
            syncComSucesso = true;
          }
          if (!captura.sefaz_consultada) {
            const erros = captura.erros ?? [];
            const msgCert = erros.find((e) => /certificado/i.test(e));
            erroMsg = msgCert
              ? 'Certificado digital não disponível/configurado para atualização DF-e.'
              : erros[0] || 'Não foi possível atualizar DF-e automaticamente.';
          } else {
            const avisos = captura.avisos ?? [];
            const mensagens = captura.mensagens ?? [];
            if (captura.ainda_tem_nsu_pendente) {
              avisoMsg =
                'Ainda há documentos pendentes na SEFAZ. Clique em "Atualizar agora" para continuar a captura.';
            } else if (captura.parou_por_limite_lotes) {
              avisoMsg =
                'Captura interrompida pelo limite de lotes. Use "Atualizar agora" para buscar mais documentos.';
            }
            const semNovos = mensagens.find((m) => /nenhum dfe novo/i.test(m));
            if (semNovos && !avisoMsg) {
              avisoMsg = semNovos;
            }
            const consumo = avisos.find((a) => /consumo indevido/i.test(a));
            if (consumo) {
              erroMsg = consumo;
              syncComSucesso = false;
            }
            const bloqueio = (captura.erros ?? []).find((e) => /consumo indevido|656/i.test(e));
            if (bloqueio) {
              erroMsg = bloqueio;
              syncComSucesso = false;
            }
          }
        } catch (err) {
          const msg = apiErrorMessage(err, {
            fallback: 'Não foi possível atualizar DF-e automaticamente.',
          });
          erroMsg = /certificado/i.test(msg)
            ? 'Certificado digital não disponível/configurado para atualização DF-e.'
            : msg;
        }

        const resumosOk = await sincronizarResumosDestinados(chavesCentralNfeRef.current, { silent: true });
        if (resumosOk) {
          syncComSucesso = true;
        } else if (!erroMsg) {
          erroMsg = 'Não foi possível consultar resumos destinados (sem envio de evento fiscal).';
        }

        await recarregarTudoRef.current();

        if (syncComSucesso) {
          const quando = registrarSincronizacao(empresaId);
          setUltimaAtualizacao(quando);
        } else {
          setUltimaAtualizacao(lerUltimaSincronizacao(empresaId));
        }
        setErroAtualizacao(erroMsg);
        setAvisoAtualizacao(avisoMsg);
      } finally {
        syncEmAndamento.current = false;
        setAtualizandoDfe(false);
      }
    },
    [empresaId, sincronizarResumosDestinados],
  );

  useEffect(() => {
    if (!empresaId) return;
    void sincronizarDfe(false);
    // Sincronização automática apenas ao abrir ou trocar empresa (intervalo mínimo via sessionStorage).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empresaId]);

  useEffect(() => {
    setFilters((prev) => {
      const next = { ...prev };
      Object.entries(extraFilters).forEach(([k, v]) => {
        next[k] = v;
      });
      ['empresa_id', 'data_emissao_inicio', 'data_emissao_fim', 'competencia_emissao', 'chave_acesso', 'ordering'].forEach((k) => {
        if (!extraFilters[k]) delete next[k];
      });
      return filtersShallowEqual(prev, next) ? prev : next;
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
        key: 'estado_consolidado',
        label: 'Estado (Inbox)',
        value: filters.estado_consolidado ?? '',
        options: ESTADOS_INBOX_FILTRO,
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

  const abrirDetalhe = (row: CentralDfeDocumento, manifestacao: NFeDestinadaDocumento | null) => {
    if (row.tipo_documento === 'NFE_ENTRADA') {
      abrirDetalheDfeNfe(row, manifestacao);
      return;
    }
    if (row.detalhe_rota) {
      window.location.assign(row.detalhe_rota);
    }
  };

  const abrirDetalheCteLocal = (row: CentralDfeDocumento) => {
    setCteDetalheLocalRow(row);
    setModalCteDetalheLocalOpen(true);
  };

  const fecharDetalheCteLocal = () => {
    setModalCteDetalheLocalOpen(false);
    setCteDetalheLocalRow(null);
  };

  const abrirConferenciaCte = (row: CentralDfeDocumento) => {
    setCteConferenciaRow(row);
    setModalCteConferenciaOpen(true);
  };

  const fecharConferenciaCte = () => {
    setModalCteConferenciaOpen(false);
    setCteConferenciaRow(null);
  };

  const fecharManifestacao = (row: NFeDestinadaDocumento | null) => {
    setManifestRow(row);
  };

  const copiarChave = async (row: CentralDfeDocumento) => {
    if (!row.chave_acesso) return;
    await copiarTextoParaAreaDeTransferencia(row.chave_acesso);
    setCopiadoId(row.id);
    window.setTimeout(() => setCopiadoId(null), 2000);
  };

  const baixarXmlArmazenado = async (row: CentralDfeDocumento) => {
    try {
      const chave = (row.chave_acesso || String(row.id)).replace(/\D/g, '').slice(0, 44) || String(row.id);
      const blob =
        row.tipo_documento === 'CTE'
          ? await cteHistoricoImportadoService.downloadXml(row.id)
          : await nfeHistoricaEntradaImportadaService.downloadXml(row.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${row.tipo_documento === 'CTE' ? 'cte' : 'nfe'}-${chave}.xml`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success('XML exportado do armazenamento local.');
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível baixar o XML armazenado.' }));
    }
  };

  const imprimirPdfArmazenado = async (row: CentralDfeDocumento) => {
    try {
      const blob =
        row.tipo_documento === 'CTE'
          ? await cteHistoricoImportadoService.dacteBlob(row.id)
          : await nfeHistoricaEntradaImportadaService.danfeBlob(row.id);
      const filename =
        row.tipo_documento === 'CTE'
          ? `DACTE_CTe_${row.id}.pdf`
          : `DANFE_NFe_Entrada_${row.id}.pdf`;
      openBlobInNewTab(blob, filename);
    } catch (e) {
      toast.error(
        apiErrorMessage(e, {
          fallback:
            row.tipo_documento === 'CTE'
              ? 'Não foi possível gerar o DACTE.'
              : 'Não foi possível gerar o DANFE.',
        }),
      );
    }
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

  return (
    <div className="erp-page">
      <PageHeader
        title="Inbox Fiscal"
        subtitle="NF-e de fornecedor e CT-e na mesma fila de recebimento. Estados consolidados refletem manifestação, conferência e estoque — sem substituir o detalhe fiscal abaixo de cada badge quando houver alerta."
        icon={Inbox}
      />

      <div className="flex flex-col gap-3 mb-4 -mt-2 text-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-muted-foreground">
          Documentos emitidos contra <strong>{empresaLabel}</strong>
          {empresaInfo?.cnpj ? ` (${fmtCnpj(empresaInfo.cnpj)})` : ''}.
          Marque &quot;Incluir já tratados&quot; para ver conferidos, divergentes, ignorados ou já lançados.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
          {atualizandoDfe && (
            <span className="inline-flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Atualizando DF-e…
            </span>
          )}
          {!atualizandoDfe && ultimaAtualizacao && (
            <span className="text-muted-foreground whitespace-nowrap">
              Última atualização: {fmtDateTime(ultimaAtualizacao)}
            </span>
          )}
          {!atualizandoDfe && erroAtualizacao && (
            <span className="text-destructive">{erroAtualizacao}</span>
          )}
          {!atualizandoDfe && !erroAtualizacao && avisoAtualizacao && (
            <span className="text-amber-700 dark:text-amber-400">{avisoAtualizacao}</span>
          )}
          {!atualizandoDfe && !erroAtualizacao && !avisoAtualizacao && (
            <span className="text-xs text-muted-foreground">
              NF-e: manifestação manual. NF-e e CT-e: armazenamento de XML manual para fechamento mensal.
            </span>
          )}
          <button
            type="button"
            className="erp-btn-ghost erp-btn-sm inline-flex w-full items-center justify-center gap-1.5 sm:w-auto"
            disabled={!empresaId || atualizandoDfe}
            onClick={() => void sincronizarDfe(true)}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Atualizar agora
          </button>
        </div>
      </div>

      {fechamento && (
        <div className="space-y-2 mb-4">
          <p className="text-sm font-medium text-muted-foreground">
            Fechamento do mês ({fmtData(fechamento.data_inicio)} — {fmtData(fechamento.data_fim)})
          </p>
          <p className="text-xs text-muted-foreground">
            NF-e exige manifestação quando aplicável; NF-e e CT-e precisam de XML armazenado na base importada.
          </p>
          <div className="grid grid-cols-1 min-[420px]:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <KpiCard label="NF-e XML armazenados" value={fechamento.nfe_xml_armazenados ?? fechamento.xml_baixados} />
            <KpiCard label="CT-e XML armazenados" value={fechamento.cte_xml_armazenados ?? 0} />
            <KpiCard label="NF-e sem manifestação" value={fechamento.sem_manifestacao} />
            <KpiCard label="NF-e XML pendente" value={fechamento.nfe_xml_pendentes_manifestacao ?? fechamento.xml_pendentes} />
            <KpiCard label="CT-e XML pendente" value={fechamento.cte_xml_pendentes ?? 0} />
            <KpiCard label="Erros armazenamento" value={fechamento.erros_armazenamento ?? fechamento.erros} />
          </div>
        </div>
      )}

      {resumo && (
        <div className="grid grid-cols-1 min-[420px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <KpiCard label="Pendentes de entrada" value={resumo.pendentes_entrada} />
          <KpiCard label="NF-e fornecedores" value={resumo.nfe_fornecedores} />
          <KpiCard label="CT-e transportadoras" value={resumo.cte_transportadoras} />
          <KpiCard label="Divergentes" value={resumo.divergentes} />
          <KpiCard label="Ignorados" value={resumo.ignorados} />
          <KpiCard label="Já tratados" value={resumo.ja_tratados} />
        </div>
      )}

      <NexusCard className="p-4 mb-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:flex lg:flex-wrap lg:items-end">
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
          <div className="min-w-0 sm:min-w-[220px]">
            <label className="erp-label">Chave de acesso</label>
            <input
              className="erp-input mt-1 w-full font-mono text-sm"
              value={chaveFiltro}
              onChange={(e) => setChaveFiltro(e.target.value)}
              placeholder="44 dígitos"
            />
          </div>
          <div className="min-w-0 sm:flex-1 sm:min-w-[200px]">
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

      <DataTableShell className="[&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border">
        {loading && <TableSkeleton rows={8} />}
        {!loading && error && <ErrorState message={error} onRetry={() => void reload()} />}
        {!loading && !error && linhasExibidas.length === 0 && (
          <EmptyState
            title="Nenhum DF-e encontrado no filtro atual"
            description={
              dataEmissaoInicio || dataEmissaoFim || competenciaEmissao
                ? `Não há documentos de fornecedores ou transportadoras para ${periodoFiltroLabel}. Tente ampliar o período, use "Atualizar agora" ou marque "Incluir já tratados".`
                : 'Não há NF-e de fornecedores ou CT-e de transportadoras pendentes contra o CNPJ da empresa. A fila é atualizada automaticamente ao abrir a tela.'
            }
          />
        )}
        {!loading && !error && linhasExibidas.length > 0 && (
          <>
            <p className="text-xs text-muted-foreground px-4 py-2 border-b border-border bg-muted/30">
              Role horizontalmente para ver todas as colunas. XML e Ações permanecem fixos à direita.
            </p>
            <DataTable mobileMode="scroll" className="min-w-[62rem] w-max [&_th]:px-3 [&_td]:px-3">
              <thead>
                <tr>
                  <th className="whitespace-nowrap w-[4.5rem]">Tipo</th>
                  <th className="whitespace-nowrap min-w-[8rem]">Documento</th>
                  <th className="max-w-[7.5rem]">Emitente</th>
                  <th className="whitespace-nowrap text-xs min-w-[8.5rem]">CNPJ emitente</th>
                  <th className="whitespace-nowrap w-[5.5rem]">Emissão</th>
                  <th className="text-right whitespace-nowrap w-[5.5rem]">Valor</th>
                  <th className="min-w-[9rem]">Estado (Inbox)</th>
                  <th className={CLASSE_COLUNA_MANIFEST_TH} title="Manifestação do Destinatário">
                    Manifest.
                  </th>
                  <th className={`whitespace-nowrap ${CLASSE_COLUNA_XML_TH}`}>XML</th>
                  <th className={`${CLASSE_COLUNA_ACOES_TH} whitespace-nowrap`}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {linhasExibidas.map(({ row, manifestacao, somenteResumo }) => {
                  const manifestacaoStatus = isCteTransportadora(row)
                    ? statusManifestacaoCteExibicao()
                    : statusManifestacaoExibicao(manifestacao, row);
                  const xmlStatus = isCteTransportadora(row)
                    ? statusXmlCteExibicao(row)
                    : statusXmlExibicao(manifestacao, row);
                  const exibirManifestar = podeManifestarNfe(manifestacao, row);
                  const exibirArmazenarXml = podeArmazenarXmlNfe(manifestacao, row);
                  const xmlArmazenado = xmlJaArmazenado(manifestacao, row);
                  const exibirAbrirBaseImportada = xmlArmazenado || podeAbrirBaseImportada(row);
                  const exibirBaixarXml = exibirAbrirBaseImportada && xmlArmazenado;
                  const exibirImprimirPdf = exibirBaixarXml;
                  const estadoInbox = resolverEstadoConsolidadoExibicao(row, manifestacao);
                  const alertasEstado = textosAlertaEstadoConsolidado(estadoInbox);
                  const alertaExcecao = ['DIVERGENTE', 'BLOQUEADO'].includes(
                    estadoInbox.estado.toUpperCase(),
                  );
                  const numeroSerie = resolverNumeroSerieInbox(row);

                  return (
                  <tr
                    key={`${somenteResumo ? 'resumo' : row.tipo_documento}-${row.id}-${row.chave_acesso}`}
                    className="group cursor-pointer hover:bg-muted/40"
                    onClick={() => abrirWorkspace(row, manifestacao, somenteResumo)}
                  >
                    <td>
                      <span className="text-sm font-medium">{row.tipo_label}</span>
                    </td>
                    <td>
                      <div className="text-sm font-medium">
                        {formatNumeroSerieInbox(row)}
                      </div>
                      {numeroSerie.viaChave ? (
                        <div
                          className="text-[10px] text-muted-foreground leading-tight"
                          title="Número e série extraídos da chave de acesso — aguardando XML para confirmação"
                        >
                          via chave
                        </div>
                      ) : numeroSerie.aguardandoXml ? (
                        <div className="text-[10px] text-muted-foreground leading-tight">resumo SEFAZ</div>
                      ) : null}
                      <div className="text-xs text-muted-foreground font-mono" title={row.chave_acesso || undefined}>
                        {row.chave_resumida || chaveNfeResumida(row.chave_acesso)}
                      </div>
                    </td>
                    <td className="text-sm max-w-[7.5rem]">
                      <span className="block truncate" title={row.emitente_nome || undefined}>
                        {row.emitente_nome || '—'}
                      </span>
                    </td>
                    <td className="text-sm font-mono">{fmtCnpj(row.emitente_cnpj)}</td>
                    <td className="text-sm whitespace-nowrap">{fmtData(row.data_emissao)}</td>
                    <td className="text-sm text-right tabular-nums">{fmtMoney(row.valor_total)}</td>
                    <td className="align-top min-w-[9rem] max-w-[14rem]">
                      <StatusBadge
                        status={badgeStatusEstadoConsolidado(estadoInbox.estado)}
                        label={estadoInbox.label}
                      />
                      {alertasEstado.length > 0 ? (
                        <div className="mt-1.5 space-y-1">
                          {alertasEstado.map((texto) => (
                            <p
                              key={texto}
                              className={`text-xs rounded border px-2 py-1 leading-snug ${
                                alertaExcecao
                                  ? 'text-orange-950 bg-orange-50 border-orange-200 dark:text-orange-100 dark:bg-orange-950/40 dark:border-orange-800'
                                  : 'text-amber-950 bg-amber-50 border-amber-200 dark:text-amber-100 dark:bg-amber-950/40 dark:border-amber-800'
                              }`}
                            >
                              {texto}
                            </p>
                          ))}
                        </div>
                      ) : null}
                      <div className="text-[10px] text-muted-foreground mt-1 leading-tight">
                        Entrada:{' '}
                        {labelStatusEntradaNfeConferenciaFinalizada(
                          row.status_entrada,
                          row.status_entrada_label,
                        )}
                      </div>
                    </td>
                    <td className={CLASSE_COLUNA_MANIFEST_TD}>
                      <StatusBadge
                        status={manifestacaoStatus.badge}
                        label={manifestacaoStatus.label}
                        className={CLASSE_BADGE_COLUNA_INBOX}
                      />
                    </td>
                    <td className={CLASSE_COLUNA_XML_TD}>
                      <StatusBadge
                        status={xmlStatus.badge}
                        label={xmlStatus.label}
                        className={CLASSE_BADGE_COLUNA_INBOX}
                      />
                    </td>
                    <td className={CLASSE_COLUNA_ACOES_TD} onClick={(e) => e.stopPropagation()}>
                      <CentralDfeAcoesLinha
                        row={row}
                        manifestacao={manifestacao}
                        somenteResumo={somenteResumo}
                        loadingAcaoManual={loadingAcaoManual}
                        copiadoId={copiadoId}
                        exibirManifestar={exibirManifestar}
                        exibirArmazenarXml={exibirArmazenarXml}
                        exibirBaixarXml={exibirBaixarXml}
                        exibirImprimirPdf={exibirImprimirPdf}
                        exibirAbrirBaseImportada={exibirAbrirBaseImportada}
                        onAbrirDetalhe={() => abrirDetalhe(row, manifestacao)}
                        onManifestar={() => void iniciarManifestacaoManual(row, manifestacao)}
                        onArmazenarXmlNfe={() => void iniciarArmazenarXmlManual(row, manifestacao, somenteResumo)}
                        onBaixarXml={() => void baixarXmlArmazenado(row)}
                        onImprimirPdf={() => void imprimirPdfArmazenado(row)}
                        onAbrirDetalheCte={() => abrirDetalheCteLocal(row)}
                        onArmazenarXmlCte={() => setConfirmArmazenarCte(row)}
                        onConferirCte={() => abrirConferenciaCte(row)}
                        onCopiarChave={() => void copiarChave(row)}
                      />
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </DataTable>
            <PaginationControls
              page={page}
              pageSize={pageSize}
              totalPages={totalPages}
              count={
                debouncedSearch
                  ? linhasExibidas.length
                  : count + manifestacaoSomenteResumo.length
              }
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          </>
        )}
      </DataTableShell>

      <ManifestacaoDestinatarioModals
        manifestRow={manifestRow}
        manifestModalKey={manifestModalKey}
        onManifestRowChange={fecharManifestacao}
        detalhe={detalhe}
        onDetalheChange={setDetalhe}
        dfeDetalheRow={dfeDetalheRow}
        onDfeDetalheRowChange={setDfeDetalheRow}
        manifestacaoDetalhe={dfeDetalheRow ? manifestacaoMap.get(dfeDetalheRow.chave_acesso) ?? null : null}
        onIniciarManifestacao={() => {
          if (!dfeDetalheRow) return;
          void iniciarManifestacaoManual(
            dfeDetalheRow,
            manifestacaoMap.get(dfeDetalheRow.chave_acesso) ?? null,
          );
        }}
        onIniciarBaixarXml={() => {
          if (!dfeDetalheRow) return;
          void iniciarArmazenarXmlManual(
            dfeDetalheRow,
            manifestacaoMap.get(dfeDetalheRow.chave_acesso) ?? null,
            false,
          );
        }}
        onAbrirManifestacaoDocumento={(doc) => {
          abrirModalManifestacao(doc);
          setDetalhe(null);
        }}
        onAbrirHistoricoDocumento={(doc) => {
          void abrirDetalheManifestacao(doc);
        }}
        confirmBaixar={confirmArmazenar?.manifestacao ?? confirmBaixar}
        onConfirmBaixarChange={(row) => {
          if (!row) {
            setConfirmArmazenar(null);
            setConfirmBaixar(null);
          }
        }}
        confirmArmazenarAberto={Boolean(confirmArmazenar)}
        loadingAcao={loadingAcaoManual}
        onExecutarManifestacao={(evento, justificativa) =>
          void executarManifestacao(evento, justificativa, () => recarregarTudo(), chavesCentralNfe)
        }
        onExecutarBaixarXml={() => void executarArmazenarXmlNfe(() => recarregarTudo(), chavesCentralNfe)}
      />

      {confirmArmazenarCte && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-background border rounded-lg p-6 max-w-md w-full space-y-4 shadow-lg">
            <h3 className="font-semibold">Armazenar XML CT-e?</h3>
            <p className="text-sm text-muted-foreground">
              O XML será confirmado na Base CT-e Importada, sem gerar financeiro, estoque, expedição, rateio ou
              apuração automática.
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" className="erp-btn-outline" onClick={() => setConfirmArmazenarCte(null)}>
                Cancelar
              </button>
              <button
                type="button"
                className="erp-btn-primary"
                disabled={loadingAcaoManual}
                onClick={() => void executarArmazenarXmlCte(() => recarregarTudo())}
              >
                Armazenar XML
              </button>
            </div>
          </div>
        </div>
      )}

      <CentralDfeCteDetalheModal
        open={modalCteDetalheLocalOpen}
        row={cteDetalheLocalRow}
        onClose={fecharDetalheCteLocal}
      />

      <CTeHistoricoDetalheModal
        cteId={cteConferenciaRow?.tipo_documento === 'CTE' ? cteConferenciaRow.id : null}
        open={modalCteConferenciaOpen}
        abaInicial="conferencia"
        onClose={fecharConferenciaCte}
        onConferenciaAtualizada={() => void recarregarTudo()}
      />

      <CentralDfeWorkspaceSheet
        open={workspaceOpen}
        row={workspaceCtx?.row ?? null}
        manifestacao={
          workspaceCtx
            ? manifestacaoMap.get(workspaceCtx.row.chave_acesso) ?? workspaceCtx.manifestacao
            : null
        }
        somenteResumo={workspaceCtx?.somenteResumo ?? false}
        loadingAcao={loadingAcaoManual}
        onClose={fecharWorkspace}
        onUpdated={recarregarTudo}
        onPrepararManifestacao={() =>
          workspaceCtx
            ? prepararManifestacaoPorDfe(workspaceCtx.row)
            : Promise.resolve(null)
        }
        onExecutarManifestacao={(evento, justificativa) =>
          executarManifestacao(evento, justificativa, () => recarregarTudo(), chavesCentralNfe)
        }
        onIniciarArmazenarXmlNfe={() => {
          if (!workspaceCtx) return;
          void iniciarArmazenarXmlManual(
            workspaceCtx.row,
            manifestacaoMap.get(workspaceCtx.row.chave_acesso) ?? workspaceCtx.manifestacao,
            workspaceCtx.somenteResumo,
          );
        }}
        onIniciarArmazenarXmlCte={() => {
          if (!workspaceCtx?.row) return;
          setConfirmArmazenarCte(workspaceCtx.row);
        }}
      />
    </div>
  );
};

export default CentralDfe;
