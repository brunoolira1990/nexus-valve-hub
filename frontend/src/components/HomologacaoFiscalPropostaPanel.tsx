import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { propostasService } from '@/services/api/comercial';
import { apiErrorMessage } from '@/services/api/config';
import type {
  CenarioFiscalSaida,
  EventoHomologacaoFiscalProposta,
  HomologacaoFiscalPropostaPayload,
  HomologacaoFiscalStatusProposta,
  ResumoHomologacaoFiscalProposta,
  StatusComparativoFiscalSaida,
  TipoEventoHomologacaoFiscal,
} from '@/types';

type Props = {
  propostaId: number;
  homologacaoStatus: HomologacaoFiscalStatusProposta;
  homologacaoObservacao?: string;
  homologacaoEm?: string | null;
  cenariosSaida: CenarioFiscalSaida[];
  onPropostaFiscalAtualizada: (patch: {
    usar_cenario_fiscal_saida: boolean;
    cenario_fiscal_saida_id: number | null;
    homologacao_fiscal_status: HomologacaoFiscalStatusProposta;
    homologacao_fiscal_observacao?: string;
    homologacao_fiscal_em?: string | null;
  }) => void;
  onItensRecalculados: () => void | Promise<void>;
};

function labelStatusHomologacao(s: HomologacaoFiscalStatusProposta): string {
  switch (s) {
    case 'NAO_INICIADA':
      return 'Não iniciada';
    case 'EM_ANALISE':
      return 'Em análise';
    case 'APROVADA':
      return 'Homologação fiscal aprovada';
    case 'REPROVADA':
      return 'Homologação reprovada';
    case 'VOLTOU_LEGADO':
      return 'Voltou ao legado';
    default:
      return s;
  }
}

function labelStatusComparativo(status: StatusComparativoFiscalSaida): string {
  switch (status) {
    case 'IGUAL':
      return 'Igual';
    case 'DIVERGENTE':
      return 'Divergente';
    case 'CENARIO_NAO_ENCONTRADO':
      return 'Cenário não encontrado';
    case 'LEGADO_NAO_ENCONTRADO':
      return 'Legado não encontrado';
    case 'AMBOS_NAO_ENCONTRADOS':
      return 'Nenhum encontrado';
    default:
      return status;
  }
}

function labelTipoEventoHomologacao(t: TipoEventoHomologacaoFiscal): string {
  switch (t) {
    case 'INICIADA':
      return 'Homologação iniciada';
    case 'RECALCULADA':
      return 'Homologação recalculada';
    case 'APROVADA':
      return 'Homologação aprovada';
    case 'REPROVADA':
      return 'Homologação reprovada';
    case 'VOLTOU_LEGADO':
      return 'Voltou para regra legada';
    case 'ALTEROU_CENARIO':
      return 'Cenário fiscal alterado';
    default:
      return t;
  }
}

function resumoCurtoEvento(resumo: ResumoHomologacaoFiscalProposta | null): string {
  if (!resumo) return '—';
  return [
    `${resumo.total_itens} itens`,
    `${resumo.iguais} iguais`,
    `${resumo.divergentes} divergentes`,
    resumo.cenario_nao_encontrado ? `${resumo.cenario_nao_encontrado} sem cenário` : null,
    resumo.legado_nao_encontrado ? `${resumo.legado_nao_encontrado} sem legado` : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

function badgeHomologacaoClass(s: HomologacaoFiscalStatusProposta): string {
  switch (s) {
    case 'APROVADA':
      return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300';
    case 'EM_ANALISE':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300';
    case 'REPROVADA':
    case 'VOLTOU_LEGADO':
      return 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300';
    default:
      return 'bg-muted text-muted-foreground';
  }
}

export function HomologacaoFiscalPropostaPanel({
  propostaId,
  homologacaoStatus,
  homologacaoObservacao = '',
  homologacaoEm,
  cenariosSaida,
  onPropostaFiscalAtualizada,
  onItensRecalculados,
}: Props) {
  const [aberto, setAberto] = useState(
    homologacaoStatus === 'EM_ANALISE' || homologacaoStatus === 'APROVADA',
  );
  const [dados, setDados] = useState<HomologacaoFiscalPropostaPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [acaoLoading, setAcaoLoading] = useState(false);
  const [observacao, setObservacao] = useState(homologacaoObservacao);
  const [cenarioId, setCenarioId] = useState<number | ''>('');
  const [historicoAberto, setHistoricoAberto] = useState(false);
  const [historicoEventos, setHistoricoEventos] = useState<EventoHomologacaoFiscalProposta[] | null>(
    null,
  );
  const [historicoLoading, setHistoricoLoading] = useState(false);
  const [historicoError, setHistoricoError] = useState<string | null>(null);

  const carregarResumo = useCallback(async () => {
    if (!propostaId) return;
    setLoading(true);
    setLoadError(null);
    try {
      const r = await propostasService.homologacaoFiscalResumo(propostaId);
      setDados(r);
    } catch (err) {
      setLoadError('Não foi possível carregar a homologação fiscal agora.');
      setDados(null);
      console.warn(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [propostaId]);

  useEffect(() => {
    setObservacao(homologacaoObservacao);
  }, [homologacaoObservacao]);

  useEffect(() => {
    if (
      homologacaoStatus !== 'NAO_INICIADA' &&
      aberto &&
      propostaId
    ) {
      void carregarResumo();
    }
  }, [homologacaoStatus, aberto, propostaId, carregarResumo]);

  const carregarHistorico = useCallback(async () => {
    if (!propostaId) return;
    setHistoricoLoading(true);
    setHistoricoError(null);
    try {
      const h = await propostasService.homologacaoFiscalHistorico(propostaId);
      setHistoricoEventos(h.eventos);
    } catch (err) {
      setHistoricoError('Não foi possível carregar o histórico da homologação agora.');
      setHistoricoEventos(null);
      console.warn(apiErrorMessage(err));
    } finally {
      setHistoricoLoading(false);
    }
  }, [propostaId]);

  const abrirHistorico = () => {
    setHistoricoAberto(true);
    if (historicoEventos === null && !historicoLoading) {
      void carregarHistorico();
    }
  };

  const aplicarPayload = async (payload: HomologacaoFiscalPropostaPayload) => {
    setDados(payload);
    if (historicoAberto) {
      void carregarHistorico();
    }
    onPropostaFiscalAtualizada({
      usar_cenario_fiscal_saida: payload.usar_cenario_fiscal_saida,
      cenario_fiscal_saida_id: payload.cenario_fiscal_saida_id,
      homologacao_fiscal_status: payload.status,
      homologacao_fiscal_observacao: payload.observacao,
      homologacao_fiscal_em: payload.homologacao_fiscal_em,
    });
    await onItensRecalculados();
  };

  const iniciar = async () => {
    setAcaoLoading(true);
    try {
      const payload = await propostasService.homologacaoFiscalIniciar(propostaId, {
        cenario_fiscal_saida_id: cenarioId === '' ? undefined : Number(cenarioId),
        observacao,
      });
      setAberto(true);
      await aplicarPayload(payload);
    } catch (err) {
      alert(apiErrorMessage(err));
    } finally {
      setAcaoLoading(false);
    }
  };

  const aprovar = async () => {
    setAcaoLoading(true);
    try {
      await aplicarPayload(await propostasService.homologacaoFiscalAprovar(propostaId, { observacao }));
    } catch (err) {
      alert(apiErrorMessage(err));
    } finally {
      setAcaoLoading(false);
    }
  };

  const reprovar = async () => {
    setAcaoLoading(true);
    try {
      await aplicarPayload(await propostasService.homologacaoFiscalReprovar(propostaId, { observacao }));
    } catch (err) {
      alert(apiErrorMessage(err));
    } finally {
      setAcaoLoading(false);
    }
  };

  const voltarLegado = async () => {
    setAcaoLoading(true);
    try {
      await aplicarPayload(
        await propostasService.homologacaoFiscalVoltarLegado(propostaId, { observacao }),
      );
    } catch (err) {
      alert(apiErrorMessage(err));
    } finally {
      setAcaoLoading(false);
    }
  };

  const recalcular = async () => {
    setAcaoLoading(true);
    try {
      await aplicarPayload(await propostasService.homologacaoFiscalRecalcular(propostaId));
    } catch (err) {
      alert(apiErrorMessage(err));
    } finally {
      setAcaoLoading(false);
    }
  };

  const status = dados?.status ?? homologacaoStatus;
  const resumo = dados?.resumo;

  return (
    <div className="md:col-span-3 rounded-md border border-border bg-muted/10">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setAberto((v) => !v)}
      >
        <span className="text-xs font-semibold">Homologação fiscal da proposta</span>
        <span className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${badgeHomologacaoClass(status)}`}>
            {labelStatusHomologacao(status)}
          </span>
          {aberto ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>

      {aberto ? (
        <div className="px-3 pb-3 space-y-3 border-t border-border/60">
          {loadError ? <p className="text-xs text-muted-foreground pt-2">{loadError}</p> : null}

          {status === 'NAO_INICIADA' || status === 'REPROVADA' || status === 'VOLTOU_LEGADO' ? (
            <div className="space-y-2 pt-2">
              <p className="text-[11px] text-muted-foreground leading-snug">
                A proposta será recalculada usando o Cenário Fiscal de Saída com fallback na regra legada.
                Outras propostas não serão afetadas.
              </p>
              {cenariosSaida.length > 1 ? (
                <div>
                  <label className="text-[10px] text-muted-foreground">Cenário</label>
                  <select
                    className="erp-select mt-1 w-full max-w-md"
                    value={cenarioId}
                    onChange={(e) => setCenarioId(e.target.value ? Number(e.target.value) : '')}
                  >
                    <option value="">Cenário padrão de saída</option>
                    {cenariosSaida.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                        {c.padrao ? ' (padrão)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              <div>
                <label className="text-[10px] text-muted-foreground">Observação (opcional)</label>
                <input
                  className="erp-input mt-1 w-full"
                  value={observacao}
                  onChange={(e) => setObservacao(e.target.value)}
                  placeholder="Homologação inicial..."
                />
              </div>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm"
                disabled={acaoLoading}
                onClick={() => void iniciar()}
              >
                {acaoLoading ? 'Iniciando…' : 'Iniciar homologação com cenário fiscal'}
              </button>
            </div>
          ) : null}

          {status === 'APROVADA' ? (
            <div className="pt-2 space-y-1">
              <p className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">
                Esta proposta usa Cenário Fiscal de Saída.
              </p>
              {homologacaoEm ? (
                <p className="text-[10px] text-muted-foreground">
                  Registrado em {new Date(homologacaoEm).toLocaleString('pt-BR')}
                </p>
              ) : null}
              {observacao ? (
                <p className="text-[11px] text-muted-foreground">Observação: {observacao}</p>
              ) : null}
            </div>
          ) : null}

          {(status === 'REPROVADA' || status === 'VOLTOU_LEGADO') && observacao ? (
            <p className="text-[11px] text-muted-foreground pt-2">Observação: {observacao}</p>
          ) : null}

          {status === 'EM_ANALISE' && resumo ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] pt-1">
                <div className="rounded border border-border/50 px-2 py-1">
                  <span className="text-muted-foreground">Iguais</span>
                  <p className="font-semibold">{resumo.iguais}</p>
                </div>
                <div className="rounded border border-border/50 px-2 py-1">
                  <span className="text-muted-foreground">Divergentes</span>
                  <p className="font-semibold text-amber-700 dark:text-amber-400">{resumo.divergentes}</p>
                </div>
                <div className="rounded border border-border/50 px-2 py-1">
                  <span className="text-muted-foreground">Sem cenário</span>
                  <p className="font-semibold">{resumo.cenario_nao_encontrado}</p>
                </div>
                <div className="rounded border border-border/50 px-2 py-1">
                  <span className="text-muted-foreground">Sem legado</span>
                  <p className="font-semibold">{resumo.legado_nao_encontrado}</p>
                </div>
              </div>
              {(resumo.itens_com_deducao_icms_base_pis_cofins > 0 ||
                resumo.itens_com_reforma_configurada > 0 ||
                resumo.itens_com_recomendacoes_nfe > 0) && (
                <p className="text-[10px] text-muted-foreground">
                  Dedução ICMS base PIS/COFINS: {resumo.itens_com_deducao_icms_base_pis_cofins} · Reforma:{' '}
                  {resumo.itens_com_reforma_configurada} · Recomendações NF-e:{' '}
                  {resumo.itens_com_recomendacoes_nfe}
                </p>
              )}
              {loading ? (
                <p className="text-xs text-muted-foreground">Carregando itens…</p>
              ) : dados?.itens?.length ? (
                <div className="overflow-x-auto max-h-48 overflow-y-auto rounded border border-border">
                  <table className="w-full text-[10px]">
                    <thead className="bg-muted/40 sticky top-0">
                      <tr>
                        <th className="text-left p-1">Produto</th>
                        <th className="text-left p-1">NCM</th>
                        <th className="text-left p-1">Origem</th>
                        <th className="text-left p-1">Comparativo</th>
                        <th className="text-left p-1">Divergências</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dados.itens.map((row) => (
                        <tr key={row.item_id} className="border-t border-border/40">
                          <td className="p-1 font-mono">{row.produto_codigo || '—'}</td>
                          <td className="p-1 font-mono">{row.ncm || '—'}</td>
                          <td className="p-1">{row.origem_oficial}</td>
                          <td className="p-1">{labelStatusComparativo(row.comparativo_status)}</td>
                          <td className="p-1">
                            {row.divergencias.length
                              ? row.divergencias.map((d) => `${d.label}: ${d.legado} → ${d.cenario}`).join('; ')
                              : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <input
                  className="erp-input flex-1 min-w-[12rem] h-8 text-xs"
                  value={observacao}
                  onChange={(e) => setObservacao(e.target.value)}
                  placeholder="Observação da decisão fiscal"
                />
                <button
                  type="button"
                  className="erp-btn-primary erp-btn-sm"
                  disabled={acaoLoading}
                  onClick={() => void aprovar()}
                >
                  Aprovar homologação
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={acaoLoading}
                  onClick={() => void reprovar()}
                >
                  Reprovar e voltar ao legado
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm inline-flex items-center gap-1"
                  disabled={acaoLoading}
                  onClick={() => void recalcular()}
                >
                  <RefreshCw className="h-3 w-3" />
                  Recalcular
                </button>
                <button
                  type="button"
                  className="erp-btn-outline erp-btn-sm"
                  disabled={acaoLoading}
                  onClick={() => void voltarLegado()}
                >
                  Voltar ao legado
                </button>
              </div>
            </>
          ) : null}

          <div className="border-t border-border/60 pt-2">
            <button
              type="button"
              className="text-[11px] font-medium text-primary hover:underline"
              onClick={() => (historicoAberto ? setHistoricoAberto(false) : abrirHistorico())}
            >
              {historicoAberto ? 'Ocultar histórico' : 'Ver histórico da homologação'}
              {dados?.total_eventos_homologacao != null && dados.total_eventos_homologacao > 0
                ? ` (${dados.total_eventos_homologacao})`
                : ''}
            </button>
            {historicoAberto ? (
              <div className="mt-2 space-y-2">
                {historicoLoading ? (
                  <p className="text-xs text-muted-foreground">Carregando histórico…</p>
                ) : historicoError ? (
                  <p className="text-xs text-muted-foreground">{historicoError}</p>
                ) : historicoEventos?.length ? (
                  <ul className="space-y-2 max-h-56 overflow-y-auto">
                    {historicoEventos.map((evt) => (
                      <li
                        key={evt.id}
                        className="rounded border border-border/50 px-2 py-1.5 text-[10px] leading-snug"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-1">
                          <span className="font-semibold">{labelTipoEventoHomologacao(evt.tipo_evento)}</span>
                          <span className="text-muted-foreground">
                            {new Date(evt.criado_em).toLocaleString('pt-BR')}
                          </span>
                        </div>
                        <p className="text-muted-foreground mt-0.5">
                          {evt.criado_por_nome ? `Por ${evt.criado_por_nome} · ` : ''}
                          Status: {labelStatusHomologacao(evt.status_resultante)}
                          {evt.cenario_fiscal_saida_nome
                            ? ` · Cenário: ${evt.cenario_fiscal_saida_nome}`
                            : evt.usar_cenario_fiscal_saida
                              ? ' · Cenário padrão'
                              : ' · Legado'}
                        </p>
                        {evt.observacao ? (
                          <p className="mt-0.5 italic text-muted-foreground">{evt.observacao}</p>
                        ) : null}
                        <p className="mt-0.5">{resumoCurtoEvento(evt.resumo)}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Nenhum evento de homologação registrado ainda.
                  </p>
                )}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
