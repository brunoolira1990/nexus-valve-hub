import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Modal } from '@/components/Modal';
import { FornecedorEntradaAcoes } from '@/components/fiscal/FornecedorEntradaAcoes';
import { DfeClassificacaoBadges } from '@/components/fiscal/DfeClassificacaoBadges';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { NexusButton } from '@/components/nexus';
import { apiErrorMessage } from '@/services/api/config';
import {
  cteHistoricoImportadoService,
  type CTeHistoricoDetalhe,
  type CTeHistoricoList,
  type CTePreviewContasPagar,
  type CTeRateioLinha,
  type CTeRateioSugestao,
} from '@/services/api/cteHistoricoImportado';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import { formatComponentesFrete, participantesCteFromDetalhe } from '@/lib/cteParticipanteFormat';
import {
  badgeClassStatusFiscalEntrada,
  labelStatusFiscalEntrada,
} from '@/lib/conferenciaNfeLabels';
import { buildCriarRegraFiscalCteUrl } from '@/lib/regrasFiscaisEntradaHelpers';

type Aba = 'resumo' | 'participantes' | 'totais' | 'docs' | 'frete' | 'eventos' | 'conferencia' | 'tecnico';

const fmtMoney = (v: unknown): string => {
  const n = Number(String(v ?? 0).replace(',', '.'));
  return `R$ ${(Number.isFinite(n) ? n : 0).toFixed(2)}`;
};

type Props = {
  open: boolean;
  cteId: number | null;
  listRow?: CTeHistoricoList | null;
  abaInicial?: Aba;
  embedded?: boolean;
  onClose: () => void;
  onConferenciaAtualizada?: () => void;
};

export function CTeHistoricoDetalheModal({
  open,
  cteId,
  listRow,
  abaInicial = 'resumo',
  embedded = false,
  onClose,
  onConferenciaAtualizada,
}: Props) {
  const [detalhe, setDetalhe] = useState<CTeHistoricoDetalhe | null>(null);
  const [aba, setAba] = useState<Aba>('resumo');
  const [erro, setErro] = useState('');
  const [busy, setBusy] = useState(false);
  const [observacao, setObservacao] = useState('');
  const [motivoDiv, setMotivoDiv] = useState('');
  const [motivoIgn, setMotivoIgn] = useState('');
  const [checklist, setChecklist] = useState({
    confirmar_tomador: false,
    confirmar_transportadora: false,
    confirmar_valores: false,
    confirmar_documentos_referenciados: false,
  });
  const [rateio, setRateio] = useState<CTeRateioSugestao | null>(null);
  const [linhasRateio, setLinhasRateio] = useState<CTeRateioLinha[]>([]);
  const [previewCp, setPreviewCp] = useState<CTePreviewContasPagar | null>(null);
  const [gerarImpostos, setGerarImpostos] = useState(true);
  const [vencimentoCp, setVencimentoCp] = useState('');

  const carregar = useCallback(async (id: number) => {
    setErro('');
    setBusy(true);
    try {
      const d = await cteHistoricoImportadoService.getById(id);
      setDetalhe(d);
      setObservacao(d.observacao_conferencia || '');
      const ck = d.checklist_conferencia_json || {};
      setChecklist({
        confirmar_tomador: Boolean(ck.confirmar_tomador),
        confirmar_transportadora: Boolean(ck.confirmar_transportadora),
        confirmar_valores: Boolean(ck.confirmar_valores),
        confirmar_documentos_referenciados: Boolean(ck.confirmar_documentos_referenciados),
      });
    } catch (e) {
      setErro(apiErrorMessage(e));
      setDetalhe(null);
    } finally {
      setBusy(false);
    }
  }, []);

  const carregarFrete = useCallback(async (id: number) => {
    try {
      const [sug, prev] = await Promise.all([
        cteHistoricoImportadoService.sugerirRateioFrete(id),
        cteHistoricoImportadoService.previewContasPagar(id).catch(() => null),
      ]);
      setRateio(sug);
      const linhasSalvas = (sug.rateio_atual?.linhas as CTeRateioLinha[] | undefined) || [];
      setLinhasRateio(linhasSalvas.length ? linhasSalvas : sug.linhas);
      setPreviewCp(prev);
      if (prev?.vencimento_sugerido) setVencimentoCp(prev.vencimento_sugerido);
    } catch (e) {
      setErro(apiErrorMessage(e));
      setRateio(null);
      setPreviewCp(null);
    }
  }, []);

  useEffect(() => {
    if ((open || embedded) && cteId) {
      setAba(abaInicial);
      void carregar(cteId);
    } else if (!open && !embedded) {
      setDetalhe(null);
      setErro('');
      setRateio(null);
      setPreviewCp(null);
    }
  }, [open, embedded, cteId, abaInicial, carregar]);

  useEffect(() => {
    if (aba === 'frete' && cteId && (open || embedded)) {
      void carregarFrete(cteId);
    }
  }, [aba, cteId, open, embedded, carregarFrete]);

  const participantes = useMemo(() => (detalhe ? participantesCteFromDetalhe(detalhe) : []), [detalhe]);
  const componentes = useMemo(
    () => formatComponentesFrete(detalhe?.componentes_frete_json),
    [detalhe?.componentes_frete_json],
  );

  const statusConf = detalhe?.status_conferencia || listRow?.status_conferencia || 'IMPORTADO';
  const podeConferir = ['IMPORTADO', 'PROCESSADO', 'PREPARADO'].includes(statusConf);
  const regraFiscal = detalhe?.regra_fiscal;
  const regraBloqueiaConferir = Boolean(regraFiscal && regraFiscal.pode_conferir === false);
  const urlCriarRegraCte = buildCriarRegraFiscalCteUrl({
    cfop: regraFiscal?.cfop_cte || detalhe?.cfop || '',
    uf_origem: detalhe?.uf_inicio || '',
    uf_destino: detalhe?.uf_fim || '',
  });

  const blocoRegraFiscal = regraFiscal ? (
    <div
      className={`rounded-lg border px-3 py-2 text-xs space-y-1 ${
        regraFiscal.status === 'OK'
          ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
          : regraFiscal.status === 'ALERTA'
            ? 'border-amber-200 bg-amber-50 text-amber-950'
            : 'border-destructive/40 bg-destructive/5 text-foreground'
      }`}
      data-testid="cte-regra-fiscal"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Regra fiscal (CFOP CT-e)</span>
        <span className={`${badgeClassStatusFiscalEntrada(regraFiscal.status || 'SEM_REGRA')} inline-block`}>
          {labelStatusFiscalEntrada(regraFiscal.status || 'SEM_REGRA')}
        </span>
        {regraFiscal.cfop_cte ? (
          <span className="text-muted-foreground font-mono">CFOP {regraFiscal.cfop_cte}</span>
        ) : null}
      </div>
      <p>{regraFiscal.mensagem}</p>
      {regraFiscal.regra_nome ? (
        <p className="text-muted-foreground">
          Regra: {regraFiscal.regra_nome}
          {regraFiscal.cfop_entrada ? ` · CFOP entrada ${regraFiscal.cfop_entrada}` : ''}
        </p>
      ) : null}
      {regraFiscal.status === 'SEM_REGRA' || regraFiscal.status === 'BLOQUEADO' ? (
        <Link to={urlCriarRegraCte} className="erp-btn-outline erp-btn-sm text-xs inline-flex mt-1">
          Cadastrar regra Frete/transporte
        </Link>
      ) : null}
    </div>
  ) : null;

  const aplicarConferencia = async (fn: () => Promise<unknown>) => {
    if (!cteId) return;
    setBusy(true);
    setErro('');
    try {
      await fn();
      await carregar(cteId);
      onConferenciaAtualizada?.();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const tituloModal = detalhe
    ? `Detalhes do CT-e importado — ${detalhe.numero}/${detalhe.serie}`
    : 'Detalhes do CT-e importado';

  const conteudo = (
    <>
      {erro ? <p className="text-sm text-destructive mb-3">{erro}</p> : null}
      {busy && !detalhe ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}
      {detalhe && (
        <div className={`space-y-4 text-sm ${embedded ? '' : 'max-h-[70vh] overflow-y-auto'}`}>
          <div className="flex flex-wrap gap-2 items-center border-b border-border pb-3">
            <StatusBadge status={statusConf.toLowerCase()} />
            <DfeClassificacaoBadges classificacao={detalhe.classificacao_dfe || listRow?.classificacao_dfe} max={5} />
            <span className="text-xs text-muted-foreground font-mono" title={detalhe.chave_acesso}>
              {chaveNfeResumida(detalhe.chave_acesso)}
            </span>
          </div>

          <div className="flex flex-wrap gap-2 border-b border-border pb-3">
            {(['resumo', 'participantes', 'totais', 'docs', 'frete', 'eventos', 'conferencia', 'tecnico'] as Aba[]).map((t) => (
              <button
                key={t}
                type="button"
                className={`erp-btn-sm ${aba === t ? 'erp-btn-primary' : 'erp-btn-outline'}`}
                onClick={() => setAba(t)}
              >
                {t === 'resumo' && 'Resumo'}
                {t === 'participantes' && 'Participantes'}
                {t === 'totais' && 'Totais / tributos'}
                {t === 'docs' && 'Documentos vinculados'}
                {t === 'frete' && 'Frete / financeiro'}
                {t === 'eventos' && 'Eventos'}
                {t === 'conferencia' && 'Conferência'}
                {t === 'tecnico' && 'Técnico / XML'}
              </button>
            ))}
          </div>

          {aba === 'resumo' && (
            <div className="space-y-3">
              {blocoRegraFiscal}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div><span className="text-muted-foreground">Transportadora</span><p>{detalhe.transportadora_nome || '—'}</p></div>
              <div><span className="text-muted-foreground">Tomador</span><p>{detalhe.empresa_tomadora_nome || '—'}</p></div>
              <div><span className="text-muted-foreground">CFOP</span><p className="font-mono">{detalhe.cfop || '—'}</p></div>
              <div><span className="text-muted-foreground">Valor serviço</span><p>{fmtMoney(detalhe.valor_total_servico)}</p></div>
              <div><span className="text-muted-foreground">Status fiscal</span><p>{detalhe.status_visual || detalhe.status_documento}</p></div>
              </div>
            </div>
          )}

          {aba === 'participantes' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {participantes.length === 0 ? (
                <p className="text-muted-foreground">Nenhum participante identificado no XML.</p>
              ) : (
                participantes.map((p) => (
                  <div key={p.papel} className="erp-card p-3">
                    <div className="text-xs font-medium text-primary">{p.papel}</div>
                    <div className="font-medium mt-1">{p.razaoSocial}</div>
                    <div className="text-xs text-muted-foreground mt-2">CNPJ/CPF: {p.documento}</div>
                    <div className="text-xs text-muted-foreground">IE: {p.ie}</div>
                    <div className="text-xs text-muted-foreground">{p.municipioUf}</div>
                    <div className="text-xs text-muted-foreground mt-1">{p.endereco}</div>
                  </div>
                ))
              )}
              {cteId ? (
                <div className="md:col-span-2">
                  <p className="text-xs font-medium text-muted-foreground mb-2">
                    {detalhe.fornecedor?.remetente_propria_empresa || detalhe.fornecedor?.status === 'propria_empresa'
                      ? 'Remetente'
                      : 'Fornecedor / remetente'}
                  </p>
                  <FornecedorEntradaAcoes
                    status={detalhe.fornecedor}
                    busy={busy}
                    onVincular={async (fornecedorId) => {
                      const res = await cteHistoricoImportadoService.vincularFornecedor(cteId, fornecedorId);
                      setDetalhe(res.cte);
                      onConferenciaAtualizada?.();
                    }}
                    onCadastrar={async (payload) => {
                      const res = await cteHistoricoImportadoService.cadastrarVincularFornecedor(cteId, payload);
                      setDetalhe(res.cte);
                      onConferenciaAtualizada?.();
                    }}
                  />
                </div>
              ) : null}
            </div>
          )}

          {aba === 'totais' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Valor total do serviço</div><div className="text-lg font-semibold">{fmtMoney(detalhe.valor_total_servico)}</div></div>
              <div className="erp-card p-3"><div className="text-xs text-muted-foreground">Valor a receber</div><div className="text-lg font-semibold">{fmtMoney(detalhe.valor_receber)}</div></div>
              <div className="erp-card p-3">
                <div className="text-xs text-muted-foreground">ICMS</div>
                <div className="text-sm font-medium">
                  Base {fmtMoney(detalhe.icms_base)} · Alíq. {Number(detalhe.icms_aliquota || 0).toFixed(2)}% · Valor{' '}
                  {fmtMoney(detalhe.icms_valor)}
                </div>
              </div>
              <div className="erp-card p-3">
                <div className="text-xs text-muted-foreground">Reforma (CBS / IBS)</div>
                {(() => {
                  const ib = (detalhe.reforma_e_outros_json as { ibscbs?: Record<string, unknown> } | undefined)?.ibscbs;
                  if (!ib || !ib.presente) {
                    return <p className="text-xs text-muted-foreground mt-1">Sem bloco IBSCBS no XML.</p>;
                  }
                  return (
                    <div className="text-sm font-medium space-y-0.5 mt-1">
                      <div>CBS {fmtMoney(ib.cbs_valor)}</div>
                      <div>IBS {fmtMoney(ib.ibs_valor)}</div>
                      {ib.cst ? <div className="text-xs text-muted-foreground">CST {String(ib.cst)}</div> : null}
                    </div>
                  );
                })()}
              </div>
              <div className="erp-card p-3 md:col-span-2">
                <div className="text-xs text-muted-foreground mb-2">Componentes do frete</div>
                {componentes.length === 0 ? <p className="text-muted-foreground text-xs">Nenhum componente detalhado.</p> : (
                  <ul className="text-xs space-y-1">
                    {componentes.map((c) => (
                      <li key={c.nome} className="flex justify-between gap-2"><span>{c.nome}</span><span>{fmtMoney(c.valor)}</span></li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {aba === 'docs' && (
            <div className="space-y-2">
              {(detalhe.documentos_vinculados_resumo || []).length === 0 && (detalhe.chaves_nfe_vinculadas || []).length === 0 ? (
                <p className="text-muted-foreground">Nenhuma NF-e referenciada no XML.</p>
              ) : (
                (detalhe.documentos_vinculados_resumo || []).map((doc) => (
                  <div key={doc.chave_acesso} className="erp-card p-3 flex flex-wrap justify-between gap-2 items-center">
                    <div>
                      <div className="font-medium text-sm">
                        {doc.numero ? `NF-e ${doc.numero}${doc.serie ? `/${doc.serie}` : ''}` : 'NF-e referenciada'}
                      </div>
                      <div className="font-mono text-xs" title={doc.chave_acesso}>{chaveNfeResumida(doc.chave_acesso)}</div>
                      <div className="text-xs text-muted-foreground mt-1">{doc.origem_label}</div>
                      {doc.nfe_entrada_status ? (
                        <div className="text-xs text-muted-foreground">Operacional: {doc.nfe_entrada_status}</div>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {doc.localizada && doc.rota_detalhe ? (
                        <Link to={doc.rota_detalhe} className="erp-btn-outline erp-btn-sm text-xs">
                          Abrir documento
                        </Link>
                      ) : null}
                      {doc.rota_operacional && doc.rota_operacional !== doc.rota_detalhe ? (
                        <Link to={doc.rota_operacional} className="erp-btn-outline erp-btn-sm text-xs">
                          Entrada operacional
                        </Link>
                      ) : null}
                      {!doc.localizada ? <StatusBadge status="fora_apuracao" /> : <StatusBadge status="importada" />}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {aba === 'frete' && (
            <div className="space-y-4" data-testid="cte-frete-financeiro">
              {blocoRegraFiscal}
              <p className="text-xs text-muted-foreground">
                Rateio assistido do frete nas NF-es referenciadas e geração explícita de Contas a Pagar (transportadora).
                Não altera estoque nem custo de produto automaticamente. Exige regra fiscal Frete/transporte para o CFOP do CT-e.
              </p>
              {rateio ? (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-medium">Rateio</span>
                    <span className="text-muted-foreground">
                      Base {fmtMoney(rateio.valor_base)} · método {rateio.metodo}
                      {rateio.rateado ? ' · salvo' : ''}
                    </span>
                    <NexusButton
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={busy || !cteId}
                      onClick={() => {
                        if (!cteId) return;
                        setBusy(true);
                        void cteHistoricoImportadoService
                          .salvarRateioFrete(cteId, { linhas: linhasRateio, metodo: rateio.metodo })
                          .then(async () => {
                            await carregar(cteId);
                            await carregarFrete(cteId);
                          })
                          .catch((e) => setErro(apiErrorMessage(e)))
                          .finally(() => setBusy(false));
                      }}
                    >
                      Salvar rateio
                    </NexusButton>
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {linhasRateio.map((linha, idx) => (
                      <div key={linha.chave_acesso} className="erp-card p-2 flex flex-wrap gap-2 items-center text-xs">
                        <span className="font-medium min-w-[6rem]">
                          {linha.numero ? `NF ${linha.numero}` : chaveNfeResumida(linha.chave_acesso)}
                        </span>
                        <span className="text-muted-foreground">{linha.percentual}%</span>
                        <input
                          className="erp-input h-7 w-28 text-xs"
                          value={linha.valor_frete}
                          onChange={(e) => {
                            const v = e.target.value;
                            setLinhasRateio((prev) =>
                              prev.map((l, i) => (i === idx ? { ...l, valor_frete: v } : l)),
                            );
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Carregando rateio… (CT-e precisa estar conferido.)</p>
              )}

              <div className="border-t border-border pt-3 space-y-2">
                <p className="text-xs font-medium">Contas a pagar</p>
                {previewCp ? (
                  <>
                    <div className="text-xs text-muted-foreground space-y-0.5">
                      <div>Credor: {previewCp.fornecedor_credor_nome || '—'} ({previewCp.fornecedor_credor_cnpj || 'sem CNPJ'})</div>
                      <div>Frete: {fmtMoney(previewCp.parcela_frete?.valor)}</div>
                      {(previewCp.tributos_sugeridos || []).map((t) => (
                        <div key={t.tipo_tributo}>
                          {t.label}: {fmtMoney(t.valor)}
                        </div>
                      ))}
                      {previewCp.motivo_bloqueio_financeiro ? (
                        <p className="text-amber-700 dark:text-amber-400">{previewCp.motivo_bloqueio_financeiro}</p>
                      ) : null}
                      {(previewCp.contas_pagar_vinculadas || []).length > 0 ? (
                        <div>
                          Já gerado:{' '}
                          {previewCp.contas_pagar_vinculadas.map((t) => `${t.numero} (${t.valor_original})`).join(', ')}
                        </div>
                      ) : null}
                    </div>
                    <label className="inline-flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={gerarImpostos}
                        onChange={(e) => setGerarImpostos(e.target.checked)}
                      />
                      Gerar impostos separados (ICMS / CBS / IBS)
                    </label>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="date"
                        className="erp-input h-8 text-xs"
                        value={vencimentoCp}
                        onChange={(e) => setVencimentoCp(e.target.value)}
                      />
                      <NexusButton
                        type="button"
                        size="sm"
                        disabled={busy || !cteId || !previewCp.pode_gerar_contas_pagar}
                        onClick={() => {
                          if (!cteId) return;
                          if (
                            !window.confirm(
                              'Gerar Contas a Pagar do frete deste CT-e? Ação explícita — não reverte estoque.',
                            )
                          ) {
                            return;
                          }
                          setBusy(true);
                          void cteHistoricoImportadoService
                            .gerarContasPagar(cteId, {
                              data_vencimento: vencimentoCp || undefined,
                              gerar_impostos_separados: gerarImpostos,
                            })
                            .then(async () => {
                              await carregar(cteId);
                              await carregarFrete(cteId);
                            })
                            .catch((e) => setErro(apiErrorMessage(e)))
                            .finally(() => setBusy(false));
                        }}
                      >
                        Gerar CP
                      </NexusButton>
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">Preview financeiro indisponível até conferência.</p>
                )}
              </div>
            </div>
          )}

          {aba === 'eventos' && (
            <div className="space-y-3">
              {(!detalhe.eventos || detalhe.eventos.length === 0) && (
                <p className="text-muted-foreground">Nenhum evento importado para este CT-e.</p>
              )}
              {detalhe.eventos?.map((ev) => (
                <details key={ev.id} className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">Evento {ev.tipo_evento}</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">{JSON.stringify(ev.evento_json, null, 2)}</pre>
                </details>
              ))}
            </div>
          )}

          {aba === 'conferencia' && (
            <div className="space-y-4">
              {blocoRegraFiscal}
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-950 text-xs">
                Esta ação apenas marca o CT-e como conferido. Não gera contas a pagar, expedição, rateio de frete ou financeiro.
                Exige regra fiscal de entrada tipo «Frete / transporte (CT-e)» para o CFOP do documento.
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {(
                  [
                    ['confirmar_tomador', 'Tomador confere com a empresa'],
                    ['confirmar_transportadora', 'Transportadora confere'],
                    ['confirmar_valores', 'Valor do frete conferido'],
                    ['confirmar_documentos_referenciados', 'NF-es referenciadas verificadas'],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="inline-flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={checklist[key]}
                      disabled={!podeConferir || busy}
                      onChange={(e) => setChecklist((p) => ({ ...p, [key]: e.target.checked }))}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <div>
                <label className="erp-label">Observações da conferência</label>
                <textarea className="erp-input mt-1 w-full min-h-[80px]" value={observacao} onChange={(e) => setObservacao(e.target.value)} disabled={busy} />
              </div>
              {statusConf === 'DIVERGENTE' && detalhe.divergencia_motivo ? (
                <p className="text-sm text-destructive">Motivo divergência: {detalhe.divergencia_motivo}</p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <NexusButton
                  type="button"
                  disabled={!podeConferir || busy || regraBloqueiaConferir}
                  onClick={() => {
                    if (!window.confirm('Marcar como conferido? Não gera financeiro, expedição ou rateio.')) return;
                    void aplicarConferencia(() =>
                      cteHistoricoImportadoService.conferir(cteId!, { observacao, ...checklist }),
                    );
                  }}
                >
                  Marcar como conferido
                </NexusButton>
                <NexusButton
                  type="button"
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    const m = motivoDiv.trim();
                    if (!m) {
                      setErro('Informe o motivo da divergência.');
                      return;
                    }
                    void aplicarConferencia(() =>
                      cteHistoricoImportadoService.marcarDivergente(cteId!, { motivo: m, observacao }),
                    );
                  }}
                >
                  Marcar como divergente
                </NexusButton>
                <NexusButton
                  type="button"
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    const m = motivoIgn.trim();
                    if (!m) {
                      setErro('Informe o motivo para ignorar.');
                      return;
                    }
                    if (!window.confirm('Ignorar operacionalmente? O CT-e permanece na base importada.')) return;
                    void aplicarConferencia(() =>
                      cteHistoricoImportadoService.ignorarOperacional(cteId!, { motivo: m, observacao }),
                    );
                  }}
                >
                  Ignorar operacionalmente
                </NexusButton>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="erp-label">Motivo divergência</label>
                  <input className="erp-input mt-1 w-full" value={motivoDiv} onChange={(e) => setMotivoDiv(e.target.value)} />
                </div>
                <div>
                  <label className="erp-label">Motivo ignorar</label>
                  <input className="erp-input mt-1 w-full" value={motivoIgn} onChange={(e) => setMotivoIgn(e.target.value)} />
                </div>
              </div>
            </div>
          )}

          {aba === 'tecnico' && (
            <div className="space-y-3">
              <details className="erp-card p-3" open>
                <summary className="cursor-pointer font-medium">Participantes (JSON)</summary>
                <pre className="mt-2 text-xs overflow-x-auto max-h-48 bg-muted rounded-md p-2">
                  {JSON.stringify(
                    {
                      emit_json: detalhe.emit_json,
                      tomador_json: detalhe.tomador_json,
                      rem_json: detalhe.rem_json,
                      dest_json: detalhe.dest_json,
                      exped_json: detalhe.exped_json,
                      receb_json: detalhe.receb_json,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
              {['totais_json', 'imposto_json', 'prot_json', 'reforma_e_outros_json', 'componentes_frete_json'].map((k) => (
                <details key={k} className="erp-card p-3">
                  <summary className="cursor-pointer font-medium">{k}</summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-40">
                    {JSON.stringify((detalhe as Record<string, unknown>)[k], null, 2)}
                  </pre>
                </details>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );

  if (embedded) {
    return conteudo;
  }

  return (
    <Modal isOpen={open} onClose={onClose} title={tituloModal} size="xl">
      {conteudo}
    </Modal>
  );
}
