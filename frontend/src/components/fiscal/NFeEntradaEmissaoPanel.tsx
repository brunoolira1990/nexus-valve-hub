import { useCallback, useEffect, useState } from 'react';
import { FileText, Loader2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
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
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PopupBlockedError } from '@/lib/downloadBlobFile';
import {
  confirmacaoProducaoValida,
  montarPayloadEmitirProducao,
  TEXTO_CONFIRMACAO_PRODUCAO,
} from '@/lib/nfeSaidaEmissaoProducao';
import { nfeEntradasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { NFeEntrada } from '@/types';

type Checklist = {
  pronta?: boolean;
  pendencias?: Array<{ codigo?: string; mensagem?: string }>;
  alertas?: Array<{ codigo?: string; mensagem?: string }>;
  mensagem?: string;
};

type Props = {
  nfe: NFeEntrada;
  onAtualizado: () => void | Promise<void>;
};

export function NFeEntradaEmissaoPanel({ nfe, onAtualizado }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [checklistHomolog, setChecklistHomolog] = useState<Checklist | null>(null);
  const [checklistProd, setChecklistProd] = useState<Checklist | null>(null);
  const [resultado, setResultado] = useState<string | null>(null);
  const [modalProd, setModalProd] = useState(false);
  const [checkboxOk, setCheckboxOk] = useState(false);
  const [textoConfirmacao, setTextoConfirmacao] = useState('');

  const autorizadaHomolog = nfe.status_emissao_sefaz === 'AUTORIZADA_HOMOLOGACAO';
  const autorizadaProd = nfe.status_emissao_sefaz === 'AUTORIZADA_PRODUCAO';
  const bloqueada = autorizadaHomolog || autorizadaProd;
  const temNumeracaoReservada = Boolean(
    (nfe.serie_nfe || '').trim() && (nfe.numero_nfe || '').trim() && (nfe.chave_acesso || '').trim(),
  );
  const numeracaoHomologTravada =
    !bloqueada &&
    (nfe.ambiente_emissao || '').toLowerCase() === 'homologacao' &&
    Boolean((nfe.chave_acesso || '').trim() || (nfe.numero_nfe || '').trim());
  const pendenciaHomologNumeracao = (checklistProd?.pendencias || []).some(
    (p) => p.codigo === 'NUMERACAO_HOMOLOG_RESERVADA',
  );
  const mostrarPrepararProducao = numeracaoHomologTravada || pendenciaHomologNumeracao;
  const ambienteAtual = (nfe.ambiente_emissao || '').toLowerCase();
  const isAmbienteProducao = ambienteAtual === 'producao';

  const carregarChecklists = useCallback(async () => {
    if (bloqueada) return;
    try {
      const [h, p] = await Promise.all([
        nfeEntradasService.validarEmissaoHomologacao(nfe.id),
        nfeEntradasService.validarEmissaoProducao(nfe.id),
      ]);
      setChecklistHomolog(h);
      setChecklistProd(p);
    } catch {
      /* checklist best-effort */
    }
  }, [nfe.id, bloqueada]);

  useEffect(() => {
    void carregarChecklists();
  }, [carregarChecklists]);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setResultado(null);
    try {
      const res = await fn();
      const msg =
        res && typeof res === 'object' && 'mensagem' in res
          ? String((res as { mensagem?: string }).mensagem || '')
          : '';
      toast.success(msg || `${label} concluído`);
      if (msg) setResultado(msg);
      await onAtualizado();
      await carregarChecklists();
    } catch (e) {
      const err = apiErrorMessage(e);
      toast.error(err);
      setResultado(err);
    } finally {
      setBusy(null);
    }
  };

  const emitirHomolog = () =>
    run('Emissão homologação', async () => {
      const res = await nfeEntradasService.emitirHomologacao(nfe.id);
      if (!res.ok && !res.autorizado) {
        throw new Error(res.mensagem || res.xmotivo || 'Emissão homologação não autorizada');
      }
      return res;
    });

  const emitirProd = () =>
    run('Emissão produção', async () => {
      const res = await nfeEntradasService.emitirProducao(nfe.id, montarPayloadEmitirProducao());
      if (!res.ok && !res.autorizado) {
        const erros = Array.isArray(res.erros) ? res.erros.map(String).filter(Boolean) : [];
        throw new Error(
          res.mensagem || res.xmotivo || erros[0] || 'Emissão produção não autorizada',
        );
      }
      return res;
    });

  const reservarNumeracao = (ambiente: 'homologacao' | 'producao') =>
    run(`Reservar numeração (${ambiente})`, async () => {
      await nfeEntradasService.update(nfe.id, { ambiente_emissao: ambiente });
      return nfeEntradasService.reservarNumeracao(nfe.id);
    });

  const abrirDanfe = async (modo: 'preview' | 'autorizado') => {
    if (modo === 'preview' && !temNumeracaoReservada) {
      toast.error(
        isAmbienteProducao
          ? 'Reserve a numeração em Produção (botão «Reservar nº») antes do Preview DANFE.'
          : 'Reserve a numeração (botão «Reservar nº») antes do Preview DANFE.',
      );
      return;
    }
    setBusy(modo === 'autorizado' ? 'DANFE autorizado' : 'Preview DANFE');
    try {
      if (modo === 'autorizado') {
        await nfeEntradasService.visualizarDanfeAutorizado(nfe.id);
      } else {
        await nfeEntradasService.visualizarDanfePreview(nfe.id);
      }
    } catch (e) {
      if (e instanceof PopupBlockedError) {
        toast.error('Pop-up bloqueado. Permita janelas deste site para ver o DANFE.');
      } else {
        toast.error(apiErrorMessage(e, { fallback: 'Não foi possível abrir o DANFE.' }));
      }
    } finally {
      setBusy(null);
    }
  };

  const prodConfirmOk = confirmacaoProducaoValida(checkboxOk, textoConfirmacao);

  return (
    <div className="nexus-card p-4 space-y-4 border border-border">
      <div>
        <h3 className="text-sm font-semibold">Emissão SEFAZ — entrada própria</h3>
        <p className="text-xs text-muted-foreground mt-1">
          Numeração compartilhada com saída (mesma série/nNF). Documento com tpNF=0.
        </p>
      </div>

      <dl className="grid sm:grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-muted-foreground">Ambiente</dt>
          <dd className="font-medium">{nfe.ambiente_emissao || '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Status SEFAZ</dt>
          <dd className="font-medium">{nfe.status_emissao_sefaz || '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Série / nNF</dt>
          <dd className="font-mono">
            {nfe.serie_nfe || '—'} / {nfe.numero_nfe || '—'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Protocolo</dt>
          <dd className="font-mono">{nfe.protocolo_autorizacao || '—'}</dd>
        </div>
      </dl>

      {resultado ? <p className="text-xs border border-border rounded p-2 bg-muted/30">{resultado}</p> : null}

      {!bloqueada ? (
        <>
          <div className="space-y-2">
            <p className="text-xs font-medium">Homologação</p>
            {checklistHomolog && !checklistHomolog.pronta ? (
              <ul className="text-xs text-destructive list-disc pl-4">
                {(checklistHomolog.pendencias || []).slice(0, 5).map((p) => (
                  <li key={p.codigo || p.mensagem}>{p.mensagem}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">Checklist homologação OK ou aguardando.</p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={!!busy}
                onClick={() => void run('Validar homologação', () => nfeEntradasService.validarEmissaoHomologacao(nfe.id))}
              >
                Validar
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={!!busy || temNumeracaoReservada}
                onClick={() => void reservarNumeracao('homologacao')}
                title={temNumeracaoReservada ? 'Numeração já reservada nesta NF-e.' : undefined}
              >
                Reservar nº
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={!!busy}
                onClick={() => void run('Preview XML', () => nfeEntradasService.previewXmlOficial(nfe.id))}
              >
                Preview XML
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs inline-flex items-center gap-1"
                disabled={!!busy}
                onClick={() => void abrirDanfe('preview')}
                title="Abre o DANFE de conferência (PDF). Requer numeração reservada."
              >
                <FileText className="h-3.5 w-3.5" />
                {busy === 'Preview DANFE' ? 'Gerando…' : 'Preview DANFE'}
              </button>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm text-xs"
                disabled={!!busy || autorizadaHomolog}
                onClick={() => void emitirHomolog()}
              >
                {busy === 'Emissão homologação' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                Emitir homologação
              </button>
            </div>
          </div>

          <div className="space-y-2 border-t border-border pt-3">
            <p className="text-xs font-medium flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5" />
              Produção SEFAZ
            </p>
            {mostrarPrepararProducao ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-950 space-y-2">
                <p>
                  Esta NF-e tem numeração de <strong>homologação</strong> reservada. Para emitir em
                  produção na <strong>mesma nota</strong>, desfaça a reserva local (sem SEFAZ) e
                  prepare o ambiente.
                </p>
                <button
                  type="button"
                  className="erp-btn-primary erp-btn-sm text-xs"
                  disabled={!!busy}
                  onClick={() =>
                    void run('Preparar para produção', async () => {
                      const res = await nfeEntradasService.prepararParaProducao(nfe.id);
                      if (!res.ok) {
                        throw new Error(res.mensagem || res.detail || 'Não foi possível preparar para produção.');
                      }
                      return res;
                    })
                  }
                >
                  {busy === 'Preparar para produção' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  Desfazer homologação e preparar produção
                </button>
              </div>
            ) : null}
            {!temNumeracaoReservada && isAmbienteProducao && !mostrarPrepararProducao ? (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                Sem série/nNF reservados — use <strong>Reservar nº</strong> para conferir o DANFE
                antes de emitir (consome a sequência real de produção).
              </p>
            ) : null}
            {checklistProd && !checklistProd.pronta ? (
              <ul className="text-xs text-destructive list-disc pl-4">
                {(checklistProd.pendencias || []).slice(0, 8).map((p) => (
                  <li key={p.codigo || p.mensagem}>{p.mensagem}</li>
                ))}
              </ul>
            ) : checklistProd?.pronta ? (
              <p className="text-xs text-muted-foreground">
                Checklist produção OK. Emissão exige permissão (admin / fiscal_nfe_producao) e
                confirmação explícita no modal.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Clique em Validar produção para ver pendências. Emissão real exige
                NFE_PRODUCAO_HABILITADA e permissão do usuário.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={!!busy || mostrarPrepararProducao}
                onClick={() =>
                  void run('Validar produção', async () => {
                    await nfeEntradasService.update(nfe.id, { ambiente_emissao: 'producao' });
                    return nfeEntradasService.validarEmissaoProducao(nfe.id);
                  })
                }
              >
                Validar produção
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={!!busy || mostrarPrepararProducao || temNumeracaoReservada}
                onClick={() => void reservarNumeracao('producao')}
                title={
                  temNumeracaoReservada
                    ? 'Numeração já reservada nesta NF-e.'
                    : 'Reserva série/nNF na sequência de produção (mesma da saída).'
                }
              >
                Reservar nº
              </button>
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs inline-flex items-center gap-1"
                disabled={!!busy}
                onClick={() => void abrirDanfe('preview')}
                title="Abre o DANFE de conferência (PDF). Exige numeração reservada em produção."
              >
                <FileText className="h-3.5 w-3.5" />
                {busy === 'Preview DANFE' ? 'Gerando…' : 'Preview DANFE'}
              </button>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm text-xs"
                disabled={!!busy || autorizadaProd || mostrarPrepararProducao}
                onClick={() => {
                  setCheckboxOk(false);
                  setTextoConfirmacao('');
                  setModalProd(true);
                }}
              >
                Emitir produção
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            NF-e já autorizada ({autorizadaProd ? 'produção' : 'homologação'}). Emissão encerrada.
          </p>
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm text-xs inline-flex items-center gap-1"
            disabled={!!busy}
            onClick={() => void abrirDanfe('autorizado')}
          >
            <FileText className="h-3.5 w-3.5" />
            {busy === 'DANFE autorizado' ? 'Gerando…' : 'Ver DANFE autorizado'}
          </button>
        </div>
      )}

      <AlertDialog open={modalProd} onOpenChange={setModalProd}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar emissão em produção</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação transmite a NF-e de entrada própria (tpNF=0) para a SEFAZ em ambiente de produção,
              consumindo a sequência numérica da saída.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3 py-2">
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={checkboxOk} onCheckedChange={(v) => setCheckboxOk(v === true)} />
              <span>Confirmo emissão real em produção SEFAZ.</span>
            </label>
            <div>
              <Label htmlFor="conf-prod-ent">Digite {TEXTO_CONFIRMACAO_PRODUCAO}</Label>
              <Input
                id="conf-prod-ent"
                className="mt-1"
                value={textoConfirmacao}
                onChange={(e) => setTextoConfirmacao(e.target.value)}
                autoComplete="off"
              />
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={!prodConfirmOk || !!busy}
              onClick={(e) => {
                e.preventDefault();
                setModalProd(false);
                void emitirProd();
              }}
            >
              Emitir produção
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
