import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw, Shield } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/Modal';
import { cn } from '@/lib/utils';
import {
  ABAS_CONFERENCIA_PROIBIDAS_NO_MODAL,
  ORDEM_GRUPOS_ALTERACAO,
  agruparAlteracoesPorItem,
  itensSemRegraDoPreview,
  labelGrupoAlteracao,
  mensagemConfirmarDesabilitado,
  mensagemPosPreview,
  podeConfirmarAplicarImpostos,
  podeExibirBotaoAtualizarImpostos,
  tooltipAtualizarImpostos,
  type AlteracaoAgrupada,
  type GrupoAlteracaoImposto,
  type ItemAlteracoesAgrupadas,
} from '@/lib/nfeSaidaAtualizarImpostos';
import { apiErrorMessage } from '@/services/api/config';
import {
  nfeSaidasService,
  type AtualizarImpostosPreviewResponse,
  type NFeSaidaConferenciaPayload,
} from '@/services/api/fiscal';

type Props = {
  nfeId: number;
  isOpen: boolean;
  onClose: () => void;
  origemComercialTravada?: boolean;
  onApplied: (conferencia: NFeSaidaConferenciaPayload) => void | Promise<void>;
};

export function NFeSaidaAtualizarImpostosModal({
  nfeId,
  isOpen,
  onClose,
  origemComercialTravada = false,
  onApplied,
}: Props) {
  const [preview, setPreview] = useState<AtualizarImpostosPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [motivo, setMotivo] = useState('Regra fiscal cadastrada após geração do rascunho');
  const [error, setError] = useState<string | null>(null);

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await nfeSaidasService.atualizarImpostosPreview(nfeId);
      setPreview(data);
    } catch (err) {
      setError(apiErrorMessage(err));
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [nfeId]);

  useEffect(() => {
    if (isOpen) void loadPreview();
  }, [isOpen, loadPreview]);

  const itensAgrupados = useMemo(() => agruparAlteracoesPorItem(preview?.itens ?? []), [preview]);
  const itensSemRegra = useMemo(() => itensSemRegraDoPreview(preview?.itens ?? []), [preview]);
  const avisoPreview = preview ? mensagemPosPreview(preview) : '';
  const podeConfirmar = podeConfirmarAplicarImpostos(preview);
  const msgConfirmarDesabilitado = mensagemConfirmarDesabilitado(preview);

  const handleAplicar = async () => {
    if (!podeConfirmar) return;
    setApplying(true);
    setError(null);
    try {
      const res = await nfeSaidasService.aplicarAtualizarImpostos(nfeId, { motivo });
      toast.success(res.mensagem || 'Impostos atualizados com sucesso.');
      await onApplied(res.conferencia);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setApplying(false);
    }
  };

  const footer = (
    <div className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center">
      <div className="flex-1 min-w-0 space-y-1">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!podeConfirmar && !loading && preview ? (
          <p className="text-xs text-muted-foreground">{msgConfirmarDesabilitado}</p>
        ) : null}
      </div>
      <div className="flex justify-end gap-2 shrink-0">
        <button type="button" className="erp-btn-outline" onClick={onClose} disabled={applying}>
          Fechar
        </button>
        <button
          type="button"
          className="erp-btn-primary"
          disabled={!podeConfirmar || applying || loading}
          title={!podeConfirmar ? msgConfirmarDesabilitado : undefined}
          onClick={() => void handleAplicar()}
        >
          {applying ? <Loader2 className="h-4 w-4 animate-spin mr-1 inline" /> : null}
          Confirmar atualização
        </button>
      </div>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Atualizar fiscal da NF-e rascunho"
      size="focus"
      stacked
      footer={footer}
    >
      <div className="space-y-5" data-testid="modal-atualizar-impostos">
        <AvisoSeguranca origemComercialTravada={origemComercialTravada} />

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : preview ? (
          <>
            {preview.bloqueado ? (
              <p className="text-sm text-destructive rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2">
                {preview.mensagem || 'Atualização bloqueada para esta NF-e.'}
              </p>
            ) : null}

            <ResumoBadges preview={preview} />

            {avisoPreview ? (
              <p className="text-sm text-amber-800 dark:text-amber-200 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 flex gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{avisoPreview}</span>
              </p>
            ) : null}

            {itensSemRegra.length > 0 ? (
              <SecaoItensSemRegra itens={itensSemRegra} />
            ) : null}

            {preview.textos_fiscais?.alteracoes?.length ? (
              <SecaoTextosFiscais textos={preview.textos_fiscais.alteracoes} />
            ) : null}

            {preview.textos_fiscais?.recomendacoes?.length ? (
              <SecaoRecomendacoesNfe recomendacoes={preview.textos_fiscais.recomendacoes} />
            ) : null}

            {preview.alertas?.length ? (
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Alertas</h3>
                <ul className="text-sm space-y-1 list-disc pl-4 text-muted-foreground">
                  {preview.alertas.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </section>
            ) : null}

            {itensAgrupados.length > 0 ? (
              <section className="space-y-4">
                <h3 className="text-sm font-semibold">Alterações por item</h3>
                <div className="space-y-4 max-h-[min(42vh,380px)] overflow-y-auto pr-1 -mr-1">
                  {itensAgrupados.map((item) => (
                    <ItemAlteracoesCard key={item.itemId} item={item} />
                  ))}
                </div>
              </section>
            ) : null}

            <section>
              <label className="erp-label text-sm">Motivo (auditoria)</label>
              <textarea
                className="erp-input mt-1 w-full min-h-[72px] text-sm"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                placeholder="Ex.: Regra fiscal cadastrada após geração do rascunho"
              />
            </section>
          </>
        ) : error ? (
          <p className="text-sm text-destructive py-8 text-center">{error}</p>
        ) : null}
      </div>
    </Modal>
  );
}

function AvisoSeguranca({ origemComercialTravada }: { origemComercialTravada: boolean }) {
  return (
    <div className="rounded-md border border-sky-500/35 bg-sky-500/10 px-3 py-3 text-sm text-sky-950 dark:text-sky-100 flex gap-2">
      <Shield className="h-5 w-5 shrink-0 text-sky-600 dark:text-sky-400" />
      <div className="space-y-1">
        <p className="font-medium">Somente dados fiscais e textos da regra serão atualizados</p>
        <p className="text-xs opacity-90">
          Impostos, CFOP, Reforma Tributária, informações adicionais e recomendações da regra. Produto, quantidade,
          preço, cliente, pedido, faturamento e transporte não serão alterados.
        </p>
        {origemComercialTravada ? (
          <p className="text-xs font-medium pt-1">Origem comercial permanece travada.</p>
        ) : null}
      </div>
    </div>
  );
}

function ResumoBadges({ preview }: { preview: AtualizarImpostosPreviewResponse }) {
  const r = preview.resumo;
  const semRegra = r.itens_sem_regra > 0;
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Resumo</h3>
      <div className="flex flex-wrap gap-2">
        <Badge label="Itens" value={r.itens_total} />
        <Badge label="Com regra" value={r.itens_com_regra} variant="ok" />
        <Badge
          label="Sem regra"
          value={r.itens_sem_regra}
          variant={semRegra ? 'warn' : 'neutral'}
        />
        <Badge label="Com alteração" value={r.itens_com_alteracao} variant={r.itens_com_alteracao > 0 ? 'ok' : 'neutral'} />
        <Badge label="Reforma configurada" value={r.reforma_configurada} variant={r.reforma_configurada > 0 ? 'ok' : 'neutral'} />
        <Badge
          label="Textos sugeridos"
          value={r.textos_fiscais_sugeridos ?? 0}
          variant={(r.textos_fiscais_sugeridos ?? 0) > 0 ? 'ok' : 'neutral'}
        />
        <Badge
          label="Recomendações"
          value={r.recomendacoes_sugeridas ?? 0}
          variant={(r.recomendacoes_sugeridas ?? 0) > 0 ? 'ok' : 'neutral'}
        />
      </div>
    </section>
  );
}

function SecaoTextosFiscais({ textos }: { textos: import('@/services/api/fiscal').TextoFiscalAlteracao[] }) {
  return (
    <section className="rounded-md border border-border p-3">
      <h3 className="text-sm font-semibold mb-2">Textos fiscais sugeridos</h3>
      <p className="text-xs text-muted-foreground mb-3">
        Campos da NF-e (informações adicionais, observações). Textos já digitados serão preservados e mesclados quando
        necessário.
      </p>
      <ul className="space-y-3 text-sm">
        {textos.map((t) => (
          <li key={t.campo} className="border-b border-border/50 pb-2 last:border-0 last:pb-0">
            <p className="font-medium">{t.label}</p>
            {t.origem ? <p className="text-xs text-muted-foreground">Origem: {t.origem}</p> : null}
            <p className="text-xs mt-1">
              <span className="text-muted-foreground line-through">{t.antes}</span>
              <span className="mx-1">→</span>
              <span className="text-emerald-700 dark:text-emerald-300 whitespace-pre-wrap">{t.depois}</span>
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SecaoRecomendacoesNfe({
  recomendacoes,
}: {
  recomendacoes: import('@/services/api/fiscal').RecomendacaoFiscalPreview[];
}) {
  return (
    <section className="rounded-md border border-sky-500/30 bg-sky-500/5 p-3">
      <h3 className="text-sm font-semibold mb-2">Recomendações NF-e / DANFE</h3>
      <ul className="space-y-2 text-sm">
        {recomendacoes.map((r) => (
          <li key={`${r.origem}-${r.codigo ?? r.mensagem}`}>
            <span className="text-xs font-medium text-muted-foreground">{r.tipo}</span>
            <p>{r.mensagem}</p>
            <p className="text-xs text-muted-foreground">{r.origem}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Badge({
  label,
  value,
  variant = 'neutral',
}: {
  label: string;
  value: number;
  variant?: 'neutral' | 'ok' | 'warn';
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs',
        variant === 'ok' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200',
        variant === 'warn' && 'border-amber-500/50 bg-amber-500/15 text-amber-900 dark:text-amber-100',
        variant === 'neutral' && 'border-border bg-muted/30',
      )}
    >
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </span>
  );
}

function SecaoItensSemRegra({
  itens,
}: {
  itens: ReturnType<typeof itensSemRegraDoPreview>;
}) {
  return (
    <section className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
      <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-100 mb-2">Itens sem regra fiscal</h3>
      <ul className="space-y-2 text-sm">
        {itens.map((it) => (
          <li key={it.item_id}>
            <span className="font-medium">{it.produto_nome}</span>
            {it.ncm ? <span className="text-muted-foreground"> · NCM {it.ncm}</span> : null}
            <p className="text-xs text-amber-800 dark:text-amber-200 mt-0.5">
              {it.alertas?.[0] || 'Nenhuma regra fiscal de saída encontrada para este item.'}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ItemAlteracoesCard({ item }: { item: ItemAlteracoesAgrupadas }) {
  const gruposVisiveis = ORDEM_GRUPOS_ALTERACAO.filter((g) => (item.grupos[g]?.length ?? 0) > 0);
  const metadados = item.grupos.metadados ?? [];
  const principais = gruposVisiveis.filter((g) => g !== 'metadados');

  return (
    <article className="rounded-md border border-border bg-muted/10 p-3">
      <header className="mb-2 pb-2 border-b border-border/60">
        <p className="font-medium text-sm leading-snug">{item.produtoNome}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {item.ncm ? `NCM ${item.ncm}` : 'NCM —'}
          {item.regraNome ? ` · ${item.regraNome}` : ''}
        </p>
      </header>
      <div className="space-y-3">
        {principais.map((grupo) => (
          <GrupoAlteracoesLista key={grupo} grupo={grupo} alteracoes={item.grupos[grupo]!} />
        ))}
        {metadados.length > 0 ? (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              Metadados da regra ({metadados.length})
            </summary>
            <GrupoAlteracoesLista grupo="metadados" alteracoes={metadados} compact />
          </details>
        ) : null}
      </div>
    </article>
  );
}

function GrupoAlteracoesLista({
  grupo,
  alteracoes,
  compact = false,
}: {
  grupo: GrupoAlteracaoImposto;
  alteracoes: AlteracaoAgrupada[];
  compact?: boolean;
}) {
  return (
    <div className={compact ? 'mt-2 pl-1' : ''}>
      {!compact ? (
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">
          {labelGrupoAlteracao(grupo)}
        </h4>
      ) : null}
      <ul className={cn('space-y-1', compact ? 'text-xs' : 'text-sm')}>
        {alteracoes.map((a) => (
          <li key={a.campo} className="flex flex-wrap gap-x-1.5 gap-y-0.5">
            <span className="text-muted-foreground shrink-0">{a.label}:</span>
            <span className="text-muted-foreground line-through decoration-muted-foreground/50">{a.antes}</span>
            <span className="text-muted-foreground">→</span>
            <span className="font-medium text-emerald-700 dark:text-emerald-300">{a.depois}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BotaoAtualizarImpostosNFe({
  nfeId,
  status,
  podeAtualizar,
  itensTotal,
  origemComercialTravada = false,
  className,
  onApplied,
}: {
  nfeId: number;
  status: string;
  podeAtualizar?: boolean;
  itensTotal: number;
  origemComercialTravada?: boolean;
  className?: string;
  onApplied: (conferencia: NFeSaidaConferenciaPayload) => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const habilitado = podeExibirBotaoAtualizarImpostos(status, podeAtualizar, itensTotal);
  const tooltip = tooltipAtualizarImpostos(status, podeAtualizar, itensTotal) || undefined;

  return (
    <>
      <button
        type="button"
        className={cn('erp-btn-outline erp-btn-sm inline-flex items-center gap-1', className)}
        disabled={!habilitado}
        title={tooltip}
        onClick={() => setOpen(true)}
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Atualizar fiscal
      </button>
      <NFeSaidaAtualizarImpostosModal
        nfeId={nfeId}
        isOpen={open}
        onClose={() => setOpen(false)}
        origemComercialTravada={origemComercialTravada}
        onApplied={onApplied}
      />
    </>
  );
}

/** Garantia em testes: modal não reutiliza abas da conferência. */
export function modalNaoExibeAbasConferencia(textoVisivel: string): boolean {
  return !ABAS_CONFERENCIA_PROIBIDAS_NO_MODAL.some((aba) => textoVisivel.includes(aba));
}
