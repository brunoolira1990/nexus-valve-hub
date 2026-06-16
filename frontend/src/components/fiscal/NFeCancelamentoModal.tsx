import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { formatMoneyBRL } from '@/lib/money';
import { nfeSaidasService, type NFeCancelamentoDadosResponse, type NFeCancelamentoResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';

export const TAMANHO_MINIMO_JUSTIFICATIVA = 15;
export const TEXTO_CONFIRMACAO_PRODUCAO = 'CANCELAR';

type Etapa = 'formulario' | 'confirmacao' | 'transmitindo' | 'resultado' | 'erro';

type Props = {
  open: boolean;
  nfeId: number | null;
  onClose: () => void;
  onCancelada?: (res: NFeCancelamentoResponse) => void;
};

function CampoResumo({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className={cn('text-sm break-words', mono && 'font-mono text-xs')}>{value || '—'}</p>
    </div>
  );
}

export function NFeCancelamentoModal({ open, nfeId, onClose, onCancelada }: Props) {
  const [etapa, setEtapa] = useState<Etapa>('formulario');
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [dados, setDados] = useState<NFeCancelamentoDadosResponse | null>(null);
  const [justificativa, setJustificativa] = useState('');
  const [confirmarProducao, setConfirmarProducao] = useState(false);
  const [textoConfirmacao, setTextoConfirmacao] = useState('');
  const [resultado, setResultado] = useState<NFeCancelamentoResponse | null>(null);

  useEffect(() => {
    if (!open || !nfeId) {
      setEtapa('formulario');
      setDados(null);
      setJustificativa('');
      setConfirmarProducao(false);
      setTextoConfirmacao('');
      setErro(null);
      setResultado(null);
      return;
    }
    setLoading(true);
    setErro(null);
    void nfeSaidasService
      .cancelamentoDados(nfeId)
      .then((payload) => {
        setDados(payload);
        if (!payload.pode_cancelar) {
          setErro(payload.motivo_bloqueio || 'Cancelamento indisponível para esta NF-e.');
        }
      })
      .catch((e) => {
        setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar dados do cancelamento.' }));
      })
      .finally(() => setLoading(false));
  }, [open, nfeId]);

  const justificativaValida = justificativa.trim().length >= TAMANHO_MINIMO_JUSTIFICATIVA;
  const confirmacaoProducaoOk = useMemo(() => {
    if (!dados?.exige_confirmacao_producao) return true;
    return confirmarProducao && textoConfirmacao.trim().toUpperCase() === TEXTO_CONFIRMACAO_PRODUCAO;
  }, [confirmarProducao, dados?.exige_confirmacao_producao, textoConfirmacao]);

  const podeAvancarConfirmacao = Boolean(dados?.pode_cancelar) && justificativaValida;

  const transmitir = async () => {
    if (!nfeId || !dados?.pode_cancelar) return;
    if (!confirmacaoProducaoOk) {
      setErro('Confirme o cancelamento em produção antes de transmitir.');
      return;
    }
    setEtapa('transmitindo');
    setErro(null);
    try {
      const res = await nfeSaidasService.cancelarNfe(nfeId, {
        justificativa: justificativa.trim(),
        confirmar_cancelamento_producao: dados.exige_confirmacao_producao ? true : undefined,
        confirmar_texto: dados.exige_confirmacao_producao ? textoConfirmacao.trim() : undefined,
      });
      setResultado(res);
      if (res.ok) {
        setEtapa('resultado');
        onCancelada?.(res);
      } else {
        setErro(res.mensagem || 'SEFAZ não aceitou o cancelamento.');
        setEtapa('erro');
      }
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Falha ao transmitir cancelamento à SEFAZ.' }));
      setEtapa('erro');
    }
  };

  const footer =
    etapa === 'formulario' ? (
      <div className="flex justify-end gap-2">
        <button type="button" className="erp-btn-outline" onClick={onClose}>
          Fechar
        </button>
        <button
          type="button"
          className="erp-btn-destructive"
          disabled={!podeAvancarConfirmacao}
          onClick={() => setEtapa('confirmacao')}
        >
          Continuar
        </button>
      </div>
    ) : etapa === 'confirmacao' ? (
      <div className="flex justify-end gap-2">
        <button type="button" className="erp-btn-outline" onClick={() => setEtapa('formulario')}>
          Voltar
        </button>
        <button
          type="button"
          className="erp-btn-destructive"
          disabled={!confirmacaoProducaoOk}
          onClick={() => void transmitir()}
        >
          Transmitir cancelamento
        </button>
      </div>
    ) : etapa === 'resultado' ? (
      <div className="flex justify-end">
        <button type="button" className="erp-btn-primary" onClick={onClose}>
          Fechar
        </button>
      </div>
    ) : etapa === 'erro' ? (
      <div className="flex justify-end gap-2">
        <button type="button" className="erp-btn-outline" onClick={onClose}>
          Fechar
        </button>
        <button type="button" className="erp-btn-outline" onClick={() => setEtapa('confirmacao')}>
          Tentar novamente
        </button>
      </div>
    ) : null;

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Cancelar NF-e"
      size="lg"
      footer={footer}
    >
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando dados…
        </div>
      ) : null}

      {dados && etapa === 'formulario' ? (
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Ambiente</p>
            <p className="text-sm font-semibold">{dados.ambiente_label}</p>
          </div>

          {dados.alerta_producao ? (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive flex gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{dados.alerta_producao}</span>
            </div>
          ) : null}

          {dados.alerta_financeiro ? (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-100 flex gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{dados.alerta_financeiro}</span>
            </div>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-md border p-3">
            <CampoResumo label="NF-e" value={dados.nfe.numero_nfe} />
            <CampoResumo label="Série" value={dados.nfe.serie_nfe} />
            <CampoResumo label="Cliente" value={dados.nfe.cliente_nome} />
            <CampoResumo label="Valor total" value={formatMoneyBRL(dados.nfe.valor_total)} />
            <CampoResumo label="Protocolo autorização" value={dados.nfe.protocolo_autorizacao} mono />
            <CampoResumo label="Chave" value={dados.nfe.chave_acesso} mono />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="justificativa-cancelamento">
              Justificativa do cancelamento <span className="text-destructive">*</span>
            </label>
            <Textarea
              id="justificativa-cancelamento"
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              rows={4}
              placeholder={`Mínimo ${TAMANHO_MINIMO_JUSTIFICATIVA} caracteres (regra SEFAZ).`}
              disabled={!dados.pode_cancelar}
            />
            <p className="text-xs text-muted-foreground">{justificativa.trim().length} caracteres</p>
          </div>

          {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        </div>
      ) : null}

      {dados && etapa === 'confirmacao' ? (
        <div className="space-y-4">
          <p className="text-sm">
            Confirme o cancelamento da NF-e <strong>{dados.nfe.numero_nfe}</strong> série{' '}
            <strong>{dados.nfe.serie_nfe}</strong> em <strong>{dados.ambiente_label}</strong>.
          </p>
          <div className="rounded-md border p-3 text-sm bg-muted/20">
            <p className="text-xs text-muted-foreground mb-1">Justificativa</p>
            <p>{justificativa.trim()}</p>
          </div>

          {dados.exige_confirmacao_producao ? (
            <div className="space-y-3 rounded-md border border-destructive/30 p-3">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={confirmarProducao}
                  onChange={(e) => setConfirmarProducao(e.target.checked)}
                />
                <span>
                  Estou ciente de que esta ação transmite cancelamento fiscal real em produção para a SEFAZ.
                </span>
              </label>
              <div className="space-y-1">
                <label className="text-sm font-medium" htmlFor="confirmar-texto-cancelar">
                  Digite <strong>{TEXTO_CONFIRMACAO_PRODUCAO}</strong> para confirmar
                </label>
                <input
                  id="confirmar-texto-cancelar"
                  className="erp-input w-full"
                  value={textoConfirmacao}
                  onChange={(e) => setTextoConfirmacao(e.target.value)}
                  autoComplete="off"
                />
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              O evento será transmitido ao ambiente de homologação da SEFAZ.
            </p>
          )}

          {erro ? <p className="text-sm text-destructive">{erro}</p> : null}
        </div>
      ) : null}

      {etapa === 'transmitindo' ? (
        <div className="flex flex-col items-center gap-3 py-10 text-sm text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          Transmitindo cancelamento à SEFAZ…
        </div>
      ) : null}

      {etapa === 'resultado' && resultado ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="h-5 w-5" />
            <p className="font-medium">Cancelamento registrado na SEFAZ</p>
          </div>
          <p className="text-sm">{resultado.mensagem}</p>
          {resultado.protocolo_cancelamento ? (
            <p className="text-sm text-muted-foreground">Protocolo: {resultado.protocolo_cancelamento}</p>
          ) : null}
        </div>
      ) : null}

      {etapa === 'erro' ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <p className="font-medium">Cancelamento não concluído</p>
          </div>
          <p className="text-sm text-destructive">{erro}</p>
        </div>
      ) : null}
    </Modal>
  );
}
