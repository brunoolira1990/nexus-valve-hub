import { toast } from 'sonner';
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { MotivoAcaoDestrutivaModal } from '@/components/comercial/MotivoAcaoDestrutivaModal';
import { FinanceiroDrawerFooterAcoes } from '@/components/financeiro/FinanceiroDrawerFooterAcoes';
import { FinanceiroDrawerHistoricoSection } from '@/components/financeiro/FinanceiroDrawerHistoricoSection';
import { FinanceiroExclusaoIndisponivel } from '@/components/financeiro/FinanceiroExclusaoIndisponivel';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { formatDateBr } from '@/lib/dateBr';
import { formatCnpjDisplay } from '@/lib/cnpj';
import {
  FINANCEIRO_CREDITO_MESSAGES,
  FINANCEIRO_FORNECEDOR_MESSAGES,
  agruparFinanceiroDrawerAcoes,
  getTituloFinanceiroAcoes,
  getTituloFinanceiroOperationalMessages,
  labelEstornoMovimentoFinanceiro,
  labelTipoLancamentoPagar,
  labelTipoTributo,
  statusBadgeFinanceiro,
  tituloModoConfig,
  tituloOperacionalDrawerTitulo,
  type TituloModo,
} from '@/lib/financeiroUi';
import { formatMoneyBRL } from '@/lib/money';
import { apiErrorMessage } from '@/services/api/config';
import { financeiroService, type BaixaFinanceira, type TituloFinanceiro } from '@/services/api/financeiro';

type Props = {
  tituloId: number | null;
  modo: TituloModo;
  open: boolean;
  onClose: () => void;
  onBaixar: (titulo: TituloFinanceiro) => void;
  onUpdated: (titulo: TituloFinanceiro) => void;
  onEditar?: (titulo: TituloFinanceiro) => void;
  onAplicarCredito?: (titulo: TituloFinanceiro) => void;
  onAbaterDevolucao?: (titulo: TituloFinanceiro) => void;
  onExcluido?: () => void;
  refreshToken?: number;
};

function operationalMessageClass(tone: 'default' | 'warning' | 'muted'): string {
  if (tone === 'warning') {
    return 'text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2';
  }
  if (tone === 'muted') {
    return 'text-sm text-muted-foreground bg-muted/50 rounded-md px-3 py-2';
  }
  return 'text-sm text-foreground bg-muted/30 border border-border rounded-md px-3 py-2';
}

export function TituloFinanceiroDetalheDrawer({
  tituloId,
  modo,
  open,
  onClose,
  onBaixar,
  onUpdated,
  onEditar,
  onAplicarCredito,
  onAbaterDevolucao,
  onExcluido,
  refreshToken = 0,
}: Props) {
  const cfg = tituloModoConfig(modo);
  const [titulo, setTitulo] = useState<TituloFinanceiro | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [excluirOpen, setExcluirOpen] = useState(false);
  const [estornoBaixaId, setEstornoBaixaId] = useState<number | null>(null);
  const [estornoBaixaTipo, setEstornoBaixaTipo] = useState<string | null>(null);
  const [acaoLoading, setAcaoLoading] = useState(false);

  const load = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const data =
        modo === 'RECEBER'
          ? await financeiroService.getContaReceber(id)
          : await financeiroService.getContaPagar(id);
      setTitulo(data);
    } catch (e) {
      setTitulo(null);
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open || !tituloId) {
      setTitulo(null);
      setError(null);
      return;
    }
    void load(tituloId);
  }, [open, tituloId, modo, refreshToken]);

  const contraparte = titulo
    ? modo === 'RECEBER'
      ? titulo.cliente_nome
      : titulo.fornecedor_nome
    : '';

  const cancelar = async (motivo: string) => {
    if (!titulo) return;
    setAcaoLoading(true);
    try {
      const res = await financeiroService.cancelarTitulo(modo, titulo.id, motivo);
      setTitulo(res.titulo);
      onUpdated(res.titulo);
    } finally {
      setAcaoLoading(false);
    }
  };

  const excluir = async (motivo: string) => {
    if (!titulo) return;
    setAcaoLoading(true);
    try {
      await financeiroService.excluirTitulo(modo, titulo.id, motivo);
      toast.success(FINANCEIRO_CREDITO_MESSAGES.tituloExcluidoSucesso);
      onExcluido?.();
      onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: FINANCEIRO_CREDITO_MESSAGES.tituloExclusaoBloqueada }));
      throw e;
    } finally {
      setAcaoLoading(false);
    }
  };

  const estornar = async (motivo: string) => {
    if (!estornoBaixaId || !titulo) return;
    setAcaoLoading(true);
    try {
      const res = await financeiroService.estornarBaixa(estornoBaixaId, motivo);
      if (res.titulo) {
        setTitulo(res.titulo);
        onUpdated(res.titulo);
      }
      const tipo = (estornoBaixaTipo || '').toUpperCase();
      if (tipo === 'USO_CREDITO') {
        toast.success(FINANCEIRO_CREDITO_MESSAGES.estornoUsoCreditoSucesso);
      } else if (tipo === 'ABATIMENTO_DEVOLUCAO') {
        toast.success(FINANCEIRO_CREDITO_MESSAGES.estornoAbatimentoSucesso);
      }
      setEstornoBaixaId(null);
      setEstornoBaixaTipo(null);
    } finally {
      setAcaoLoading(false);
    }
  };

  const abrirEstorno = (baixa: BaixaFinanceira) => {
    setEstornoBaixaId(baixa.id);
    setEstornoBaixaTipo(baixa.tipo_movimento ?? null);
  };

  const primeiraBaixaAtiva = titulo?.baixas?.find((b) => !b.estornada && b.pode_estornar !== false);

  const operational = titulo ? getTituloFinanceiroOperationalMessages(titulo, modo) : null;
  const acoes = titulo ? getTituloFinanceiroAcoes(titulo, modo) : [];

  const executarAcao = (id: (typeof acoes)[number]['id']) => {
    if (!titulo) return;
    switch (id) {
      case 'baixar':
        onBaixar(titulo);
        break;
      case 'editar':
        if (onEditar) onEditar(titulo);
        else toast.info('Edição de título disponível em breve.');
        break;
      case 'excluir':
        setExcluirOpen(true);
        break;
      case 'cancelar':
        setCancelOpen(true);
        break;
      case 'estornar_baixa':
        if (primeiraBaixaAtiva) abrirEstorno(primeiraBaixaAtiva);
        break;
      case 'aplicar_credito':
        onAplicarCredito?.(titulo);
        break;
      case 'abater_devolucao':
        onAbaterDevolucao?.(titulo);
        break;
      default:
        break;
    }
  };

  const grupos = agruparFinanceiroDrawerAcoes(acoes, (id) => executarAcao(id as (typeof acoes)[number]['id']));

  return (
    <>
      <Drawer open={open} onOpenChange={(v) => !v && onClose()}>
        <DrawerContent className="max-h-[92vh]">
          <DrawerHeader className="border-b border-border pb-3">
            <DrawerTitle className="flex flex-wrap items-center gap-2">
              {titulo ? (
                <>
                  <span>{tituloOperacionalDrawerTitulo(titulo, modo)}</span>
                  <StatusBadge status={statusBadgeFinanceiro(titulo)} />
                </>
              ) : (
                'Detalhe do título'
              )}
            </DrawerTitle>
            {titulo?.numero ? (
              <p className="text-xs text-muted-foreground">
                {titulo.numero}
                {titulo.origem_exibicao ? ` · ${titulo.origem_exibicao}` : ''}
              </p>
            ) : null}
          </DrawerHeader>

          <div className="overflow-y-auto px-4 py-4 space-y-6 flex-1">
            {loading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            {titulo && !loading ? (
              <>
                {operational?.messages.map((msg) => (
                  <p key={msg} className={operationalMessageClass(operational.tone)}>
                    {msg}
                  </p>
                ))}

                {titulo.alerta_origem_cancelada ? (
                  <p className={operationalMessageClass('warning')}>{titulo.alerta_origem_cancelada}</p>
                ) : null}

                {!titulo.pode_excluir && titulo.motivo_bloqueio_exclusao ? (
                  <FinanceiroExclusaoIndisponivel motivo={titulo.motivo_bloqueio_exclusao} />
                ) : null}

                <section>
                  <h3 className="text-sm font-semibold mb-2">Dados principais</h3>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    {modo === 'PAGAR' && titulo.tipo_lancamento ? (
                      <>
                        <dt className="text-muted-foreground">Tipo</dt>
                        <dd>{labelTipoLancamentoPagar(titulo.tipo_lancamento, titulo.tipo_lancamento_label)}</dd>
                      </>
                    ) : null}
                    {titulo.descricao ? (
                      <>
                        <dt className="text-muted-foreground">Descrição</dt>
                        <dd className="font-medium">{titulo.descricao}</dd>
                      </>
                    ) : null}
                    {titulo.tipo_tributo ? (
                      <>
                        <dt className="text-muted-foreground">Tributo</dt>
                        <dd>{labelTipoTributo(titulo.tipo_tributo, titulo.tipo_tributo_label)}</dd>
                      </>
                    ) : null}
                    {titulo.competencia ? (
                      <>
                        <dt className="text-muted-foreground">Competência</dt>
                        <dd>{formatDateBr(titulo.competencia)}</dd>
                      </>
                    ) : null}
                    {titulo.periodo_apuracao ? (
                      <>
                        <dt className="text-muted-foreground">Período de apuração</dt>
                        <dd>{titulo.periodo_apuracao}</dd>
                      </>
                    ) : null}
                    {contraparte ? (
                      <>
                        <dt className="text-muted-foreground">{cfg.contraparteLabel}</dt>
                        <dd className="font-medium">
                          {contraparte}
                          {modo === 'RECEBER' && titulo.cliente_cnpj ? (
                            <span className="block text-xs text-muted-foreground tabular-nums font-normal">
                              {formatCnpjDisplay(titulo.cliente_cnpj)}
                            </span>
                          ) : null}
                          {modo === 'PAGAR' && titulo.fornecedor_cnpj ? (
                            <span className="block text-xs text-muted-foreground tabular-nums font-normal">
                              {formatCnpjDisplay(titulo.fornecedor_cnpj)}
                            </span>
                          ) : null}
                        </dd>
                      </>
                    ) : modo === 'PAGAR' && titulo.tipo_lancamento === 'DESPESA_OPERACIONAL' ? (
                      <>
                        <dt className="text-muted-foreground">{cfg.contraparteLabel}</dt>
                        <dd className="text-muted-foreground">{FINANCEIRO_FORNECEDOR_MESSAGES.semFornecedor}</dd>
                      </>
                    ) : null}
                    <dt className="text-muted-foreground">Vencimento</dt>
                    <dd>{formatDateBr(titulo.data_vencimento)}</dd>
                    <dt className="text-muted-foreground">Valor original</dt>
                    <dd>{formatMoneyBRL(titulo.valor_original)}</dd>
                    <dt className="text-muted-foreground">{cfg.valorPagoLabel}</dt>
                    <dd>{formatMoneyBRL(titulo.valor_baixado)}</dd>
                    <dt className="text-muted-foreground">{cfg.saldoLabel}</dt>
                    <dd className="font-semibold">{formatMoneyBRL(titulo.valor_aberto)}</dd>
                    <dt className="text-muted-foreground">Status</dt>
                    <dd>{statusBadgeFinanceiro(titulo)}</dd>
                    {titulo.categoria_nome ? (
                      <>
                        <dt className="text-muted-foreground">Categoria</dt>
                        <dd>{titulo.categoria_nome}</dd>
                      </>
                    ) : null}
                  </dl>
                  {titulo.observacoes ? (
                    <p className="mt-3 text-sm text-muted-foreground whitespace-pre-wrap">{titulo.observacoes}</p>
                  ) : null}
                </section>

                {titulo.origem_nfe_detalhe ? (
                  <section>
                    <h3 className="text-sm font-semibold mb-2">Origem</h3>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                      <dt className="text-muted-foreground">Documento</dt>
                      <dd>{titulo.origem_exibicao || `NF-e nº ${titulo.origem_nfe_detalhe.numero_nfe}`}</dd>
                      {titulo.origem_nfe_detalhe.chave_acesso ? (
                        <>
                          <dt className="text-muted-foreground">Chave NF-e</dt>
                          <dd className="font-mono text-xs break-all">{titulo.origem_nfe_detalhe.chave_acesso}</dd>
                        </>
                      ) : null}
                      {titulo.origem_nfe_detalhe.pedido_venda_numero ? (
                        <>
                          <dt className="text-muted-foreground">Pedido</dt>
                          <dd>{titulo.origem_nfe_detalhe.pedido_venda_numero}</dd>
                        </>
                      ) : null}
                      {titulo.origem_nfe_detalhe.faturamento_numero ? (
                        <>
                          <dt className="text-muted-foreground">Faturamento</dt>
                          <dd>{titulo.origem_nfe_detalhe.faturamento_numero}</dd>
                        </>
                      ) : null}
                    </dl>
                  </section>
                ) : null}

                {titulo.origem_nfe_entrada_detalhe ? (
                  <section>
                    <h3 className="text-sm font-semibold mb-2">Origem</h3>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                      <dt className="text-muted-foreground">Documento</dt>
                      <dd>
                        {titulo.origem_exibicao ||
                          `NF-e Entrada nº ${titulo.origem_nfe_entrada_detalhe.numero_nfe}`}
                      </dd>
                      {titulo.origem_nfe_entrada_detalhe.fornecedor_nome ? (
                        <>
                          <dt className="text-muted-foreground">Fornecedor</dt>
                          <dd>{titulo.origem_nfe_entrada_detalhe.fornecedor_nome}</dd>
                        </>
                      ) : null}
                      {titulo.origem_nfe_entrada_detalhe.chave_acesso ? (
                        <>
                          <dt className="text-muted-foreground">Chave NF-e</dt>
                          <dd className="font-mono text-xs break-all">
                            {titulo.origem_nfe_entrada_detalhe.chave_acesso}
                          </dd>
                        </>
                      ) : null}
                      {titulo.origem_nfe_entrada_detalhe.pedido_compra_numero ? (
                        <>
                          <dt className="text-muted-foreground">Pedido de compra</dt>
                          <dd>{titulo.origem_nfe_entrada_detalhe.pedido_compra_numero}</dd>
                        </>
                      ) : null}
                      {titulo.origem_nfe_entrada_detalhe.data_emissao ? (
                        <>
                          <dt className="text-muted-foreground">Emissão</dt>
                          <dd>{formatDateBr(titulo.origem_nfe_entrada_detalhe.data_emissao)}</dd>
                        </>
                      ) : null}
                      {titulo.origem_nfe_entrada_detalhe.data_importacao ? (
                        <>
                          <dt className="text-muted-foreground">Importação</dt>
                          <dd>{formatDateBr(titulo.origem_nfe_entrada_detalhe.data_importacao.slice(0, 10))}</dd>
                        </>
                      ) : null}
                    </dl>
                  </section>
                ) : null}

                {titulo.parcelas && titulo.parcelas.length > 0 ? (
                  <section>
                    <h3 className="text-sm font-semibold mb-2">Parcelas</h3>
                    <div className="overflow-x-auto rounded-md border border-border">
                      <table className="erp-table text-sm">
                        <thead>
                          <tr>
                            <th>Nº</th>
                            <th>Vencimento</th>
                            <th>Valor</th>
                            <th>Saldo</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {titulo.parcelas.map((p) => (
                            <tr key={p.id}>
                              <td>{String(p.numero_parcela).padStart(3, '0')}</td>
                              <td>{formatDateBr(p.data_vencimento)}</td>
                              <td>{formatMoneyBRL(p.valor_original)}</td>
                              <td>{formatMoneyBRL(p.valor_aberto)}</td>
                              <td>
                                <StatusBadge status={p.status_label || p.status} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ) : null}

                {titulo.baixas && titulo.baixas.length > 0 ? (
                  <section>
                    <h3 className="text-sm font-semibold mb-2">Movimentos</h3>
                    <ul className="space-y-2">
                      {titulo.baixas.map((b) => (
                        <li
                          key={b.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3 text-sm"
                        >
                          <div>
                            <p className="font-medium">
                              {b.tipo_movimento_label || b.tipo_movimento || 'Movimento'} —{' '}
                              {formatDateBr(b.data_baixa)} — {formatMoneyBRL(b.valor)}
                            </p>
                            <p className="text-muted-foreground text-xs">
                              {b.forma_pagamento_nome || b.forma_pagamento_label || b.forma_pagamento_codigo}
                              {b.conta_financeira_nome ? ` · ${b.conta_financeira_nome}` : ''}
                              {b.estornada ? ' · Estornada' : ' · Ativo'}
                            </p>
                            {b.observacoes ? (
                              <p className="text-xs text-muted-foreground mt-1">{b.observacoes}</p>
                            ) : null}
                            {b.estornada && b.motivo_estorno ? (
                              <p className="text-xs text-muted-foreground mt-1">Estorno: {b.motivo_estorno}</p>
                            ) : null}
                          </div>
                          {b.pode_estornar ? (
                            <button
                              type="button"
                              className="erp-btn-outline erp-btn-sm"
                              onClick={() => abrirEstorno(b)}
                            >
                              {labelEstornoMovimentoFinanceiro(b.tipo_movimento)}
                            </button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </section>
                ) : null}

                {titulo.eventos && titulo.eventos.length > 0 ? (
                  <FinanceiroDrawerHistoricoSection
                    eventos={titulo.eventos}
                    possuiMovimentoAtivo={Boolean(titulo.possui_movimento_financeiro_ativo)}
                    resumoMovimento={
                      titulo.possui_baixa_ativa
                        ? 'Este título possui movimentos financeiros ativos.'
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

      <MotivoAcaoDestrutivaModal
        open={excluirOpen}
        onOpenChange={setExcluirOpen}
        title="Excluir título?"
        description={FINANCEIRO_CREDITO_MESSAGES.exclusaoTituloDescricao}
        detalhes={
          titulo?.possui_apenas_movimentos_estornados ? (
            <p className="text-sm rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-900 px-3 py-2">
              {FINANCEIRO_CREDITO_MESSAGES.exclusaoTituloAvisoEstorno}
            </p>
          ) : undefined
        }
        confirmLabel="Excluir título"
        loading={acaoLoading}
        onConfirm={excluir}
      />

      <MotivoAcaoDestrutivaModal
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancelar título"
        description="O título será cancelado e não aceitará novas baixas."
        confirmLabel="Cancelar título"
        loading={acaoLoading}
        onConfirm={cancelar}
      />

      <MotivoAcaoDestrutivaModal
        open={estornoBaixaId != null}
        onOpenChange={(v) => {
          if (!v) {
            setEstornoBaixaId(null);
            setEstornoBaixaTipo(null);
          }
        }}
        title={labelEstornoMovimentoFinanceiro(estornoBaixaTipo)}
        description={
          estornoBaixaTipo === 'USO_CREDITO'
            ? 'O uso de crédito será estornado. O saldo do título e do crédito será reaberto.'
            : estornoBaixaTipo === 'ABATIMENTO_DEVOLUCAO'
              ? 'O abatimento será estornado e o saldo do título será reaberto.'
              : 'A baixa será estornada e o saldo do título será reaberto.'
        }
        confirmLabel="Confirmar estorno"
        loading={acaoLoading}
        onConfirm={estornar}
      />
    </>
  );
}
