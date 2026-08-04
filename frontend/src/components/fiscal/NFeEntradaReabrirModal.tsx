import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { apiErrorMessage } from '@/services/api/config';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import type {
  PreviewReaberturaEntradaFornecedor,
  ResultadoReaberturaEntradaFornecedor,
} from '@/types';

const MOTIVO_MINIMO = 10;

type Props = {
  open: boolean;
  nfeHistoricaId: number | null;
  onOpenChange: (open: boolean) => void;
  onSuccess: (resultado: ResultadoReaberturaEntradaFornecedor) => void | Promise<void>;
};

const RESUMO_LABELS: Array<
  [keyof PreviewReaberturaEntradaFornecedor['resumo_vinculos'], string]
> = [
  ['pedido_compra_selecionado', 'Pedido de Compra selecionado'],
  ['estoque_aplicado', 'Estoque aplicado'],
  ['baixa_pedido_compra_aplicada', 'Baixa do Pedido de Compra'],
  ['contas_pagar_vinculadas', 'Contas a Pagar vinculadas'],
  ['alocacoes_entrada_venda', 'Alocações Entrada × Venda'],
  ['atendimentos_estoque', 'Atendimentos de estoque'],
  ['barras_estoque_nao_canceladas', 'Barras de estoque ativas'],
  ['itens_com_produto', 'Itens com produto vinculado'],
  ['equivalencias', 'Equivalências'],
  ['splits_corrida', 'Divisões por corrida/lote'],
  ['certificados_fornecedor', 'Certificados de Fornecedor'],
];

function valorResumo(value: boolean | number | null | undefined): string {
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não';
  if (value === null || value === undefined) return '0';
  return String(value);
}

export function NFeEntradaReabrirModal({
  open,
  nfeHistoricaId,
  onOpenChange,
  onSuccess,
}: Props) {
  const [preview, setPreview] = useState<PreviewReaberturaEntradaFornecedor | null>(null);
  const [motivo, setMotivo] = useState('');
  const [loading, setLoading] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState('');

  useEffect(() => {
    if (!open || !nfeHistoricaId) {
      setPreview(null);
      setMotivo('');
      setErro('');
      return;
    }
    let cancelado = false;
    setLoading(true);
    setErro('');
    void nfeEntradaConferenciaService
      .previewReabertura(nfeHistoricaId)
      .then((data) => {
        if (!cancelado) setPreview(data);
      })
      .catch((error) => {
        if (!cancelado) setErro(apiErrorMessage(error));
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });
    return () => {
      cancelado = true;
    };
  }, [open, nfeHistoricaId]);

  const fechar = () => {
    if (enviando) return;
    onOpenChange(false);
  };

  const confirmar = async () => {
    if (!nfeHistoricaId || !preview?.pode_reabrir) return;
    const motivoLimpo = motivo.trim();
    if (motivoLimpo.length < MOTIVO_MINIMO) {
      setErro(`Informe um motivo com pelo menos ${MOTIVO_MINIMO} caracteres.`);
      return;
    }
    setEnviando(true);
    setErro('');
    try {
      const resultado = await nfeEntradaConferenciaService.reabrir(nfeHistoricaId, motivoLimpo);
      await onSuccess(resultado);
      onOpenChange(false);
    } catch (error) {
      setErro(apiErrorMessage(error));
    } finally {
      setEnviando(false);
    }
  };

  const motivoValido = motivo.trim().length >= MOTIVO_MINIMO;

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? onOpenChange(true) : fechar())}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Reabrir entrada de fornecedor para correção</DialogTitle>
          <DialogDescription>
            Reabre somente a conferência operacional interna do Nexus.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-sm">
          <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-amber-900 dark:text-amber-100">
            Esta ação reabre somente a conferência interna do Nexus. Ela não cancela, não altera e não
            transmite eventos para a NF-e emitida pelo fornecedor.
          </p>
          <p className="rounded-md border border-border bg-muted/40 px-3 py-2">
            Estoque, Pedido de Compra, Contas a Pagar e alocações não serão revertidos por esta ação.
          </p>

          {loading ? <p className="text-muted-foreground">Verificando efeitos operacionais…</p> : null}

          {preview ? (
            <>
              <div className="grid sm:grid-cols-2 gap-2 rounded-md border p-3">
                <p><strong>NF-e:</strong> {preview.numero_nfe || '—'}{preview.serie_nfe ? ` / ${preview.serie_nfe}` : ''}</p>
                <p><strong>Fornecedor:</strong> {preview.fornecedor || '—'}</p>
                <p><strong>Estado atual:</strong> {preview.estado_atual || 'Sem conferência'}</p>
                <p><strong>Conferência:</strong> {preview.conferencia_id ?? '—'}</p>
              </div>

              {preview.impedimentos.length ? (
                <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3">
                  <p className="font-medium text-destructive">A reabertura está bloqueada:</p>
                  <ul className="mt-2 list-disc pl-5 space-y-1">
                    {preview.impedimentos.map((item) => (
                      <li key={item.codigo}>{item.mensagem}</li>
                    ))}
                  </ul>
                  {preview.impedimentos.some((i) => i.codigo === 'ALOCACAO_ENTRADA_VENDA') ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      «Salvar com pendências» não remove alocação. Feche este modal, desvincule em
                      «Alocar para venda» e abra de novo «Reabrir para correção».
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-emerald-800 dark:text-emerald-200">
                  Nenhum efeito que exija estorno foi encontrado.
                </p>
              )}

              <div className="rounded-md border p-3">
                <p className="font-medium mb-2">Resumo dos vínculos encontrados</p>
                <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-1">
                  {RESUMO_LABELS.map(([key, label]) => (
                    <div key={key} className="flex justify-between gap-3">
                      <dt className="text-muted-foreground">{label}</dt>
                      <dd className="font-medium">{valorResumo(preview.resumo_vinculos[key])}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <p className="text-muted-foreground">{preview.orientacao}</p>
            </>
          ) : null}

          <div className="space-y-1">
            <label htmlFor="motivo-reabertura-entrada" className="text-xs font-medium">
              Motivo da reabertura
            </label>
            <textarea
              id="motivo-reabertura-entrada"
              className="erp-input w-full min-h-[88px]"
              value={motivo}
              onChange={(event) => setMotivo(event.target.value)}
              placeholder="Descreva a correção operacional necessária"
              disabled={enviando || !preview?.pode_reabrir}
            />
            <p className="text-xs text-muted-foreground">Mínimo de {MOTIVO_MINIMO} caracteres.</p>
          </div>

          {erro ? <p role="alert" className="text-sm text-destructive">{erro}</p> : null}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <button type="button" className="erp-btn-outline" disabled={enviando} onClick={fechar}>
            Fechar
          </button>
          <button
            type="button"
            className="erp-btn-primary"
            disabled={loading || enviando || !preview?.pode_reabrir || !motivoValido}
            onClick={() => void confirmar()}
          >
            {enviando ? 'Reabrindo…' : 'Reabrir entrada para correção'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
