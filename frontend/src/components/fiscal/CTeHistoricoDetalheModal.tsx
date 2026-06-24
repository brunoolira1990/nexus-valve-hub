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
} from '@/services/api/cteHistoricoImportado';
import { chaveNfeResumida } from '@/lib/chaveNfeResumida';
import { formatComponentesFrete, participantesCteFromDetalhe } from '@/lib/cteParticipanteFormat';

type Aba = 'resumo' | 'participantes' | 'totais' | 'docs' | 'eventos' | 'conferencia' | 'tecnico';

const fmtMoney = (v: unknown): string => {
  const n = Number(String(v ?? 0).replace(',', '.'));
  return `R$ ${(Number.isFinite(n) ? n : 0).toFixed(2)}`;
};

type Props = {
  open: boolean;
  cteId: number | null;
  listRow?: CTeHistoricoList | null;
  abaInicial?: Aba;
  onClose: () => void;
  onConferenciaAtualizada?: () => void;
};

export function CTeHistoricoDetalheModal({
  open,
  cteId,
  listRow,
  abaInicial = 'resumo',
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

  useEffect(() => {
    if (open && cteId) {
      setAba(abaInicial);
      void carregar(cteId);
    } else if (!open) {
      setDetalhe(null);
      setErro('');
    }
  }, [open, cteId, abaInicial, carregar]);

  const participantes = useMemo(() => (detalhe ? participantesCteFromDetalhe(detalhe) : []), [detalhe]);
  const componentes = useMemo(
    () => formatComponentesFrete(detalhe?.componentes_frete_json),
    [detalhe?.componentes_frete_json],
  );

  const statusConf = detalhe?.status_conferencia || listRow?.status_conferencia || 'IMPORTADO';
  const podeConferir = ['IMPORTADO', 'PROCESSADO', 'PREPARADO'].includes(statusConf);

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

  return (
    <Modal isOpen={open} onClose={onClose} title={tituloModal} size="xl">
      {erro ? <p className="text-sm text-destructive mb-3">{erro}</p> : null}
      {busy && !detalhe ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}
      {detalhe && (
        <div className="space-y-4 text-sm max-h-[70vh] overflow-y-auto">
          <div className="flex flex-wrap gap-2 items-center border-b border-border pb-3">
            <StatusBadge status={statusConf.toLowerCase()} />
            <DfeClassificacaoBadges classificacao={detalhe.classificacao_dfe || listRow?.classificacao_dfe} max={5} />
            <span className="text-xs text-muted-foreground font-mono" title={detalhe.chave_acesso}>
              {chaveNfeResumida(detalhe.chave_acesso)}
            </span>
          </div>

          <div className="flex flex-wrap gap-2 border-b border-border pb-3">
            {(['resumo', 'participantes', 'totais', 'docs', 'eventos', 'conferencia', 'tecnico'] as Aba[]).map((t) => (
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
                {t === 'eventos' && 'Eventos'}
                {t === 'conferencia' && 'Conferência'}
                {t === 'tecnico' && 'Técnico / XML'}
              </button>
            ))}
          </div>

          {aba === 'resumo' && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div><span className="text-muted-foreground">Transportadora</span><p>{detalhe.transportadora_nome || '—'}</p></div>
              <div><span className="text-muted-foreground">Tomador</span><p>{detalhe.empresa_tomadora_nome || '—'}</p></div>
              <div><span className="text-muted-foreground">Valor serviço</span><p>{fmtMoney(detalhe.valor_total_servico)}</p></div>
              <div><span className="text-muted-foreground">Status fiscal</span><p>{detalhe.status_visual || detalhe.status_documento}</p></div>
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
                  <p className="text-xs font-medium text-muted-foreground mb-2">Fornecedor / remetente</p>
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
                <div className="text-sm font-medium">Base {fmtMoney(detalhe.icms_base)} | Valor {fmtMoney(detalhe.icms_valor)}</div>
              </div>
              <div className="erp-card p-3">
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
                      <div className="font-mono text-xs" title={doc.chave_acesso}>{chaveNfeResumida(doc.chave_acesso)}</div>
                      <div className="text-xs text-muted-foreground mt-1">{doc.origem_label}</div>
                    </div>
                    {doc.localizada && doc.origem === 'BASE_NFE_ENTRADA_IMPORTADA' && doc.documento_id ? (
                      <Link to="/nfe-entrada-historica-importada" className="erp-btn-outline erp-btn-sm text-xs">
                        Ver base entrada
                      </Link>
                    ) : null}
                    {doc.localizada && doc.origem === 'BASE_NFE_SAIDA_IMPORTADA' && doc.documento_id ? (
                      <Link to="/nfe-historica-importada" className="erp-btn-outline erp-btn-sm text-xs">
                        Ver base saída
                      </Link>
                    ) : null}
                    {!doc.localizada ? <StatusBadge status="fora_apuracao" /> : <StatusBadge status="importada" />}
                  </div>
                ))
              )}
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
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-950 text-xs">
                Esta ação apenas marca o CT-e como conferido. Não gera contas a pagar, expedição, rateio de frete ou financeiro.
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
                  disabled={!podeConferir || busy}
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
    </Modal>
  );
}
