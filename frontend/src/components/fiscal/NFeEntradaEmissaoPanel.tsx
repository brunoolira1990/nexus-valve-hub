import { useCallback, useEffect, useState } from 'react';
import { Loader2, ShieldAlert } from 'lucide-react';
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
        throw new Error(res.mensagem || res.xmotivo || 'Emissão produção não autorizada');
      }
      return res;
    });

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
                disabled={!!busy}
                onClick={() =>
                  void run('Reservar numeração', async () => {
                    await nfeEntradasService.update(nfe.id, { ambiente_emissao: 'homologacao' });
                    return nfeEntradasService.reservarNumeracao(nfe.id);
                  })
                }
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
            {checklistProd && !checklistProd.pronta ? (
              <ul className="text-xs text-destructive list-disc pl-4">
                {(checklistProd.pendencias || []).slice(0, 5).map((p) => (
                  <li key={p.codigo || p.mensagem}>{p.mensagem}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">
                Exige flag NFE_PRODUCAO_HABILITADA e permissão do usuário.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={!!busy}
                onClick={() =>
                  void run('Preparar produção', async () => {
                    await nfeEntradasService.update(nfe.id, { ambiente_emissao: 'producao' });
                    return nfeEntradasService.validarEmissaoProducao(nfe.id);
                  })
                }
              >
                Validar produção
              </button>
              <button
                type="button"
                className="erp-btn-primary erp-btn-sm text-xs"
                disabled={!!busy || autorizadaProd}
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
        <p className="text-xs text-muted-foreground">
          NF-e já autorizada ({autorizadaProd ? 'produção' : 'homologação'}). Emissão encerrada.
        </p>
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
