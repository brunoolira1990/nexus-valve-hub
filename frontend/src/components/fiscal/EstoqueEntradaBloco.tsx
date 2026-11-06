import { forwardRef, useImperativeHandle, useState } from 'react';
import { toast } from 'sonner';

import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';
import { apiErrorMessage } from '@/services/api/config';
import type { ResultadoAplicacaoEstoque } from '@/types';

/**
 * Bloco de ESTOQUE da entrada de fornecedor (PR 9 da Fase 2).
 *
 * Quarta extração da ordem do PR 5 e a primeira em que o wrapper precisa CRIAR o componente
 * que enrola: diferente da reabertura (PR 6), da devolução (PR 7) e do financeiro (PR 8b),
 * aqui não existia modal autocontido — o "Aplicar estoque físico" era JSX inline do painel
 * (109 linhas) com os dois fetches nos handlers do painel. O bloco é dono dos 5 estados
 * locais (H14-H18 do mapeamento: open, preview, confirmarAlertas, obs, erro), do preview
 * (`previewAplicarEstoque`) e da aplicação (`aplicarEstoque`).
 *
 * Burro no sentido do padrão: ZERO `acoes.*` e ZERO `dados.itens`. A FASE 0 mediu que o
 * updateItem por item pertence à TABELA (PR 11), não a este bloco, então o wrapper não
 * recebe a lista de itens — recebe apenas o `dataEntrada` (escalar que o payload de aplicar
 * lê de `dados`) e o `busy` (que os botões do overlay usam para `disabled`, igual quando
 * o JSX vivia no painel).
 *
 * Os quatro callbacks cobrem exatamente as linhas do disco que mutavam estado compartilhado,
 * na ordem original: `onValidarAbrir` guarda a data de entrada ANTES de abrir (:260-263);
 * `onSalvarSilencioso` persiste e aplica `setDados` (:270-271); `onAplicado` faz
 * setDados+hydrateProdutoCache OU load (:313-318) e é-awaited antes do fechamento;
 * `onConcluido` é o `notifyUpdated()` (:327). O `onBusyChange` é a ponte para
 * `acoes.setBusy` — os 2 fetches acontecem aqui dentro, então a janela de busy precisa
 * atravessar a fronteira para os botões do rodapé continuarem desabilitados.
 *
 * Os toasts da baixa de pedido (:321-326) ficam no wrapper: usam só o `res` e o `toast`,
 * nenhum estado compartilhado.
 */
export type EstoqueEntradaBlocoProps = {
  nfId: number;
  /** `estado.busy` do painel — desabilita Cancelar/Confirmar enquanto a aplicação roda. */
  busy: boolean;
  /** `dados?.data_entrada`: o payload de aplicar lê este escalar, não a lista de itens. */
  dataEntrada: string | null | undefined;
  onBusyChange: (busy: boolean) => void;
  /**
   * Guard do gatilho. `false` = o painel já registrou o erro ("informe a data de entrada")
   * e o modal NÃO abre — preserva a ordem do disco, onde a validação vem antes do setOpen.
   */
  onValidarAbrir: () => boolean;
  /** Salvar silencioso + `acoes.setDados(saved)`; lança para o catch do bloco. */
  onSalvarSilencioso: () => Promise<void>;
  /** Mutação de store do sucesso, antes do fechamento do modal. */
  onAplicado: (res: ResultadoAplicacaoEstoque) => Promise<void>;
  /** `notifyUpdated()` do painel, depois dos toasts da baixa. */
  onConcluido: () => void;
};

export type EstoqueEntradaBlocoHandle = {
  abrir: () => void;
};

export const EstoqueEntradaBloco = forwardRef<EstoqueEntradaBlocoHandle, EstoqueEntradaBlocoProps>(
  function EstoqueEntradaBloco(
    { nfId, busy, dataEntrada, onBusyChange, onValidarAbrir, onSalvarSilencioso, onAplicado, onConcluido },
    ref,
  ) {
    const [open, setOpen] = useState(false);
    const [preview, setPreview] = useState<ResultadoAplicacaoEstoque | null>(null);
    const [confirmarAlertas, setConfirmarAlertas] = useState(false);
    const [obs, setObs] = useState('');
    const [erro, setErro] = useState('');

    const fechar = () => {
      setOpen(false);
      setPreview(null);
      setErro('');
    };

    const abrir = async () => {
      if (!nfId) return;
      if (!onValidarAbrir()) return;
      setOpen(true);
      setErro('');
      setConfirmarAlertas(false);
      setObs('');
      onBusyChange(true);
      try {
        await onSalvarSilencioso();
        const next = await nfeEntradaConferenciaService.previewAplicarEstoque(nfId, false);
        setPreview(next);
      } catch (e: unknown) {
        setErro(apiErrorMessage(e));
        setPreview(null);
      } finally {
        onBusyChange(false);
      }
    };

    useImperativeHandle(ref, () => ({ abrir: () => void abrir() }), [nfId, onValidarAbrir, onSalvarSilencioso, onBusyChange]);

    const confirmar = async () => {
      if (!nfId) return;
      onBusyChange(true);
      setErro('');
      try {
        const res = await nfeEntradaConferenciaService.aplicarEstoque(nfId, {
          confirmar_alertas: confirmarAlertas,
          observacao: obs,
          data_entrada: dataEntrada || undefined,
        });
        await onAplicado(res);
        setOpen(false);
        setPreview(null);
        const baixa = res.pedido_compra_baixa;
        if (baixa?.aplicado) {
          toast.success(baixa.mensagem || 'Pedido de compra baixado.');
        } else if (baixa?.ja_baixado) {
          toast.info(baixa.mensagem || 'Pedido de compra já estava baixado para esta NF-e.');
        }
        onConcluido();
      } catch (e: unknown) {
        const err = e as { response?: { data?: ResultadoAplicacaoEstoque & { detail?: string } } };
        const data = err.response?.data;
        if (data?.pendencias || data?.alertas) {
          setPreview(data);
          setErro(data.detail || 'Não foi possível aplicar estoque físico.');
        } else {
          setErro(apiErrorMessage(e));
        }
      } finally {
        onBusyChange(false);
      }
    };

    return open && preview ? (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="erp-card max-w-3xl w-full max-h-[90vh] overflow-y-auto p-4 sm:p-6 space-y-4">
          <h2 className="text-lg font-semibold">Aplicar estoque físico</h2>
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">
            Esta ação incrementa o estoque físico em EstoqueCorrida e não deve ser executada duas vezes.
          </p>
          {erro ? (
            <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{erro}</p>
          ) : null}
          {preview.itens_aplicados.length > 0 ? (
            <div>
              <h3 className="text-sm font-medium mb-2">Itens que serão aplicados ({preview.itens_aplicados.length})</h3>
              <ul className="text-xs space-y-1 max-h-40 overflow-y-auto border rounded p-2">
                {preview.itens_aplicados.map((it, idx) => (
                  <li key={`${it.item_conferencia_id}-${it.split_ordem ?? 0}-${idx}`}>
                    Item #{it.item_conferencia_id}
                    {it.split_ordem != null ? ` · split ${it.split_ordem}` : ''}
                    {' — produto '}
                    {it.produto_id}
                    {' — corrida '}
                    {it.corrida}
                    {' — qtd '}
                    {it.quantidade}
                    {it.lote ? ` — lote ${it.lote}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {preview.itens_ignorados.length > 0 ? (
            <div>
              <h3 className="text-sm font-medium mb-2 text-muted-foreground">Não movimentam estoque</h3>
              <ul className="text-xs space-y-1 max-h-32 overflow-y-auto">
                {preview.itens_ignorados.map((it) => (
                  <li key={it.item_conferencia_id ?? it.motivo}>
                    #{it.item_conferencia_id}: {it.motivo}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {preview.alertas.length > 0 ? (
            <div className="text-sm text-amber-800">
              <h3 className="font-medium mb-1">Alertas</h3>
              <ul className="list-disc pl-5 text-xs">
                {preview.alertas.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
              <label className="flex items-center gap-2 mt-2 text-xs">
                <input
                  type="checkbox"
                  checked={confirmarAlertas}
                  onChange={(e) => setConfirmarAlertas(e.target.checked)}
                />
                Confirmo a aplicação mesmo com alertas
              </label>
            </div>
          ) : null}
          {preview.pendencias.length > 0 ? (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">
              <h3 className="font-medium mb-1">Pendências bloqueantes</h3>
              <ul className="list-disc pl-5 text-xs">
                {preview.pendencias.map((pend, i) => (
                  <li key={i}>
                    Item #{pend.item_conferencia_id}: {pend.motivo}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <label className="block text-xs">
            Observação (opcional)
            <textarea
              className="erp-input w-full mt-1 min-h-[60px]"
              value={obs}
              onChange={(e) => setObs(e.target.value)}
            />
          </label>
          <div className="flex flex-col-reverse sm:flex-row justify-end items-stretch sm:items-center gap-2">
            <button
              type="button"
              className="erp-btn-outline w-full sm:w-auto justify-center"
              onClick={fechar}
              disabled={busy}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="erp-btn-primary w-full sm:w-auto justify-center bg-emerald-700 hover:bg-emerald-800"
              onClick={() => void confirmar()}
              disabled={
                busy ||
                preview.pendencias.length > 0 ||
                (preview.alertas.length > 0 && !confirmarAlertas)
              }
            >
              Confirmar aplicação
            </button>
          </div>
        </div>
      </div>
    ) : null;
  },
);
