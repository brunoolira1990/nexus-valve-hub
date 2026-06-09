import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { CreditoEditarModal } from '@/components/financeiro/CreditoEditarModal';
import { FinanceiroDrawerFooterAcoes } from '@/components/financeiro/FinanceiroDrawerFooterAcoes';
import { FinanceiroDrawerHistoricoSection } from '@/components/financeiro/FinanceiroDrawerHistoricoSection';
import { FinanceiroExclusaoIndisponivel } from '@/components/financeiro/FinanceiroExclusaoIndisponivel';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { formatDateBr } from '@/lib/dateBr';
import { formatCnpjDisplay } from '@/lib/cnpj';
import {
  FINANCEIRO_CREDITO_MESSAGES,
  agruparFinanceiroDrawerAcoes,
  creditoOperacionalDrawerTitulo,
  getCreditoFinanceiroAcoes,
  labelCreditoOrigem,
  labelCreditoStatus,
  labelCreditoTipo,
  type CreditoFinanceiroAcaoId,
} from '@/lib/financeiroUi';
import { formatMoneyBRL } from '@/lib/money';
import { apiErrorMessage } from '@/services/api/config';
import { financeiroService, type CreditoFinanceiro } from '@/services/api/financeiro';

type Props = {
  creditoId: number | null;
  open: boolean;
  onClose: () => void;
  onUpdated: () => void;
  onAplicar: (credito: CreditoFinanceiro) => void;
  onExcluido?: () => void;
};

export function CreditoDetalheDrawer({
  creditoId,
  open,
  onClose,
  onUpdated,
  onAplicar,
  onExcluido,
}: Props) {
  const [credito, setCredito] = useState<CreditoFinanceiro | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [excluirOpen, setExcluirOpen] = useState(false);
  const [editarOpen, setEditarOpen] = useState(false);
  const [estornoOpen, setEstornoOpen] = useState(false);
  const [acaoLoading, setAcaoLoading] = useState(false);

  const load = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      setCredito(await financeiroService.getCredito(id));
    } catch (e) {
      setCredito(null);
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open || !creditoId) {
      setCredito(null);
      setError(null);
      return;
    }
    void load(creditoId);
  }, [open, creditoId]);

  const cancelar = async (motivo: string) => {
    if (!credito) return;
    setAcaoLoading(true);
    try {
      const res = await financeiroService.cancelarCredito(credito.id, motivo);
      setCredito(res);
      toast.success(FINANCEIRO_CREDITO_MESSAGES.creditoCanceladoSucesso);
      onUpdated();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: FINANCEIRO_CREDITO_MESSAGES.creditoUtilizadoCancelar }));
      throw e;
    } finally {
      setAcaoLoading(false);
    }
  };

  const excluir = async (motivo: string) => {
    if (!credito) return;
    setAcaoLoading(true);
    try {
      await financeiroService.excluirCredito(credito.id, motivo);
      toast.success(FINANCEIRO_CREDITO_MESSAGES.creditoExcluidoSucesso);
      onExcluido?.();
      onUpdated();
      onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: FINANCEIRO_CREDITO_MESSAGES.creditoExclusaoBloqueada }));
      throw e;
    } finally {
      setAcaoLoading(false);
    }
  };

  const estornarUso = async (motivo: string) => {
    if (!credito) return;
    const baixa = credito.movimentos?.find(
      (m) => !m.estornada && m.pode_estornar !== false && m.tipo_movimento === 'USO_CREDITO',
    );
    if (!baixa) return;
    setAcaoLoading(true);
    try {
      const res = await financeiroService.estornarBaixa(baixa.id, motivo);
      if (res.credito) setCredito(res.credito);
      else if (creditoId) await load(creditoId);
      toast.success(FINANCEIRO_CREDITO_MESSAGES.estornoUsoCreditoSucesso);
      onUpdated();
    } catch (e) {
      toast.error(apiErrorMessage(e));
      throw e;
    } finally {
      setAcaoLoading(false);
    }
  };

  const executarAcao = (id: CreditoFinanceiroAcaoId) => {
    if (!credito) return;
    if (id === 'aplicar') {
      onAplicar(credito);
      return;
    }
    if (id === 'editar') {
      setEditarOpen(true);
      return;
    }
    if (id === 'excluir') {
      setExcluirOpen(true);
      return;
    }
    if (id === 'cancelar') {
      setCancelOpen(true);
      return;
    }
    if (id === 'estornar_uso') {
      setEstornoOpen(true);
      return;
    }
  };

  const acoes = credito ? getCreditoFinanceiroAcoes(credito) : [];
  const grupos = agruparFinanceiroDrawerAcoes(acoes, (id) => executarAcao(id as CreditoFinanceiroAcaoId));

  return (
    <>
      <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
        <DrawerContent className="max-h-[92vh]">
          <DrawerHeader className="border-b border-border pb-3">
            <DrawerTitle className="flex flex-wrap items-center gap-2">
              {credito ? (
                <>
                  <span>{creditoOperacionalDrawerTitulo(credito)}</span>
                  <StatusBadge status={labelCreditoStatus(credito.status, credito.status_label)} />
                </>
              ) : (
                'Detalhe do crédito'
              )}
            </DrawerTitle>
            {credito ? (
              <p className="text-xs text-muted-foreground">Registro #{credito.id}</p>
            ) : null}
          </DrawerHeader>

          <div className="overflow-y-auto px-4 py-4 space-y-6 flex-1">
            {loading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            {credito && !loading ? (
              <>
                {!credito.pode_excluir && credito.motivo_bloqueio_exclusao ? (
                  <FinanceiroExclusaoIndisponivel motivo={credito.motivo_bloqueio_exclusao} />
                ) : null}

                <section>
                  <h3 className="text-sm font-semibold mb-2">Dados principais</h3>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <dt className="text-muted-foreground">Tipo</dt>
                    <dd>{labelCreditoTipo(credito.tipo, credito.tipo_label)}</dd>
                    <dt className="text-muted-foreground">{credito.tipo === 'CLIENTE' ? 'Cliente' : 'Fornecedor'}</dt>
                    <dd className="font-medium">
                      {credito.contraparte_nome || '—'}
                      {credito.cliente_cnpj ? (
                        <span className="block text-xs text-muted-foreground tabular-nums font-normal">
                          {formatCnpjDisplay(credito.cliente_cnpj)}
                        </span>
                      ) : null}
                      {credito.fornecedor_cnpj ? (
                        <span className="block text-xs text-muted-foreground tabular-nums font-normal">
                          {formatCnpjDisplay(credito.fornecedor_cnpj)}
                        </span>
                      ) : null}
                    </dd>
                    <dt className="text-muted-foreground">Origem</dt>
                    <dd>{labelCreditoOrigem(credito.origem_tipo, credito.origem_tipo_label)}</dd>
                    <dt className="text-muted-foreground">Documento de referência</dt>
                    <dd>{credito.origem_numero || '—'}</dd>
                    <dt className="text-muted-foreground">Data</dt>
                    <dd>{formatDateBr(credito.data_credito)}</dd>
                    <dt className="text-muted-foreground">Valor original</dt>
                    <dd>{formatMoneyBRL(credito.valor_original)}</dd>
                    <dt className="text-muted-foreground">Utilizado</dt>
                    <dd>{formatMoneyBRL(credito.valor_utilizado)}</dd>
                    <dt className="text-muted-foreground">Saldo</dt>
                    <dd className="font-semibold">{formatMoneyBRL(credito.saldo)}</dd>
                    <dt className="text-muted-foreground">Status</dt>
                    <dd>{labelCreditoStatus(credito.status, credito.status_label)}</dd>
                    <dt className="text-muted-foreground">Motivo</dt>
                    <dd>{credito.motivo}</dd>
                  </dl>
                  {credito.observacoes ? (
                    <div className="mt-3">
                      <p className="text-xs text-muted-foreground mb-1">Observações</p>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">{credito.observacoes}</p>
                    </div>
                  ) : null}
                  {credito.motivo_cancelamento ? (
                    <div className="mt-3">
                      <p className="text-xs text-muted-foreground mb-1">Motivo do cancelamento</p>
                      <p className="text-sm whitespace-pre-wrap">{credito.motivo_cancelamento}</p>
                    </div>
                  ) : null}
                </section>

                {credito.eventos && credito.eventos.length > 0 ? (
                  <FinanceiroDrawerHistoricoSection
                    eventos={credito.eventos}
                    possuiMovimentoAtivo={Boolean(credito.possui_movimento_ativo)}
                    resumoMovimento={
                      credito.possui_aplicacao_ativa
                        ? 'Este crédito possui aplicação ativa em título.'
                        : undefined
                    }
                  />
                ) : null}
              </>
            ) : null}
          </div>

          <FinanceiroDrawerFooterAcoes {...grupos} />
        </DrawerContent>
      </Drawer>

      <CreditoEditarModal
        open={editarOpen}
        onClose={() => setEditarOpen(false)}
        credito={credito}
        onUpdated={(c) => {
          setCredito(c);
          onUpdated();
        }}
      />

      <MotivoAcaoDestrutivaModal
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancelar crédito"
        description="O crédito será cancelado e permanecerá no histórico. Informe o motivo operacional."
        confirmLabel="Cancelar crédito"
        loading={acaoLoading}
        onConfirm={cancelar}
      />

      <MotivoAcaoDestrutivaModal
        open={excluirOpen}
        onOpenChange={setExcluirOpen}
        title="Excluir crédito?"
        description={FINANCEIRO_CREDITO_MESSAGES.exclusaoCreditoDescricao}
        detalhes={
          credito?.possui_apenas_movimentos_estornados ? (
            <p className="text-sm rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-900 px-3 py-2">
              {FINANCEIRO_CREDITO_MESSAGES.exclusaoCreditoAvisoEstorno}
            </p>
          ) : undefined
        }
        confirmLabel="Excluir crédito"
        loading={acaoLoading}
        onConfirm={excluir}
      />

      <MotivoAcaoDestrutivaModal
        open={estornoOpen}
        onOpenChange={setEstornoOpen}
        title="Estornar uso de crédito"
        description="O uso de crédito será estornado. O saldo do título e do crédito será reaberto."
        confirmLabel="Confirmar estorno"
        loading={acaoLoading}
        onConfirm={estornarUso}
      />
    </>
  );
}
