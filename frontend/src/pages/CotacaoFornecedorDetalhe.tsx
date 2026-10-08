import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, CheckCircle2, RefreshCw, Send } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { DataTable, DataTableShell } from '@/components/nexus/DataTable';
import { StatusBadge } from '@/components/nexus/StatusBadge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { descricaoItemCotacao, labelOrigemCotacao, labelStatusCotacao, respostaPodeSerSelecionada } from '@/lib/cotacaoFornecedores';
import { formatDateBr } from '@/lib/dateBr';
import { formatMoneyBRL } from '@/lib/numberFields';
import { apiErrorMessage } from '@/services/api/config';
import { cotacoesFornecedoresService } from '@/services/api/comercial';
import type {
  CotacaoComparativo,
  CotacaoComparativoItem,
  CotacaoFornecedor,
  CotacaoFornecedorHistorico,
  CotacaoFornecedorRespostaItem,
} from '@/types';

type RespostaDraft = {
  preco_unitario: string;
  preco_unitario_bruto: string;
  desconto: string;
  quantidade_atendida: string;
  unidade_cotada: string;
  fator_conversao: string;
  prazo_entrega: string;
  frete: string;
  frete_tipo: string;
  ipi_custo: string;
  icms_st_custo: string;
  outros_tributos_custo: string;
  despesas_adicionais: string;
  status_item: string;
};

const emptyDraft = (): RespostaDraft => ({
  preco_unitario: '',
  preco_unitario_bruto: '',
  desconto: '',
  quantidade_atendida: '',
  unidade_cotada: '',
  fator_conversao: '',
  prazo_entrega: '',
  frete: '',
  frete_tipo: '',
  ipi_custo: '',
  icms_st_custo: '',
  outros_tributos_custo: '',
  despesas_adicionais: '',
  status_item: 'RESPONDIDO',
});

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return formatDateBr(value) || '—';
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function money(value: number | string | null | undefined): string {
  if (value == null || value === '') return '—';
  return formatMoneyBRL(Number(value));
}

function RespostaEconomica({
  resposta,
  item,
  onSelect,
  selecting,
}: {
  resposta: CotacaoFornecedorRespostaItem;
  item: CotacaoComparativoItem;
  onSelect: (respostaId: number) => void;
  selecting: boolean;
}) {
  const calculo = resposta.calculo_custo;
  return (
    <article className="min-w-0 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h4 className="truncate font-semibold">{resposta.fornecedor_nome}</h4>
          <p className="text-xs text-muted-foreground">{labelStatusCotacao(resposta.status_item)}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {resposta.menor_preco ? <span className="rounded-full bg-amber-100 px-2 py-1 text-[11px] font-semibold text-amber-900">MENOR PREÇO</span> : null}
          {resposta.melhor_custo_total ? <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-900">MELHOR CUSTO TOTAL</span> : null}
          <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${resposta.custo_incompleto ? 'bg-red-100 text-red-900' : 'bg-emerald-50 text-emerald-800'}`}>
            {resposta.custo_incompleto ? 'CUSTO INCOMPLETO' : 'COMPLETA PARA CÁLCULO'}
          </span>
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div><dt className="text-xs text-muted-foreground">Preço líquido</dt><dd className="font-medium">{money(resposta.preco_unitario)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Preço bruto</dt><dd className="font-medium">{money(resposta.preco_unitario_bruto)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Quantidade atendida</dt><dd className="font-medium">{resposta.quantidade_atendida} {resposta.unidade_cotada || item.unidade}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Frete</dt><dd className="font-medium">{resposta.frete_tipo_codigo || resposta.frete_tipo || '—'} · {money(resposta.frete)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Custo total estimado</dt><dd className="font-semibold">{money(calculo?.custo_total_estimado)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Custo unitário efetivo</dt><dd className="font-semibold">{money(calculo?.custo_unitario_efetivo)}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Prazo</dt><dd className="font-medium">{resposta.prazo_entrega || '—'}</dd></div>
        <div><dt className="text-xs text-muted-foreground">Desconto</dt><dd className="font-medium">{money(resposta.desconto)}</dd></div>
      </dl>

      <details className="mt-4 rounded-md bg-muted/30 p-3 text-sm">
        <summary className="cursor-pointer font-medium">Tributos e composição do custo</summary>
        <div className="mt-2 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
          <p>IPI de custo: <span className="text-foreground">{money(resposta.ipi_custo)}</span></p>
          <p>ICMS-ST: <span className="text-foreground">{money(resposta.icms_st_custo)}</span></p>
          <p>Outros tributos: <span className="text-foreground">{money(resposta.outros_tributos_custo)}</span></p>
          <p>Despesas adicionais: <span className="text-foreground">{money(resposta.despesas_adicionais)}</span></p>
          {resposta.fator_conversao ? <p>Fator de conversão: <span className="text-foreground">{resposta.fator_conversao}</span></p> : null}
        </div>
      </details>

      {resposta.custo_incompleto && resposta.motivos_incompletude?.length ? (
        <p className="mt-3 text-xs text-red-700 dark:text-red-300">Motivos: {resposta.motivos_incompletude.join('; ')}</p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {resposta.selecionada_como_referencia ? (
          <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
            <CheckCircle2 className="h-4 w-4" /> Referência selecionada
          </span>
        ) : null}
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm"
          disabled={selecting || !respostaPodeSerSelecionada(resposta)}
          onClick={() => onSelect(resposta.id)}
        >
          Usar como referência
        </button>
      </div>
    </article>
  );
}

export default function CotacaoFornecedorDetalhe() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const cotacaoId = Number(id);
  const [cotacao, setCotacao] = useState<CotacaoFornecedor | null>(null);
  const [comparativo, setComparativo] = useState<CotacaoComparativo | null>(null);
  const [historico, setHistorico] = useState<CotacaoFornecedorHistorico[]>([]);
  const [drafts, setDrafts] = useState<Record<string, RespostaDraft>>({});
  const [activeTab, setActiveTab] = useState('resumo');
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!Number.isFinite(cotacaoId) || cotacaoId <= 0) {
      setError('Cotação inválida.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [detail, compare, history] = await Promise.all([
        cotacoesFornecedoresService.getById(cotacaoId),
        cotacoesFornecedoresService.comparativo(cotacaoId),
        cotacoesFornecedoresService.historico(cotacaoId),
      ]);
      setCotacao(detail);
      setComparativo(compare);
      setHistorico(history);
    } catch (err) {
      setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar a cotação.' }));
    } finally {
      setLoading(false);
    }
  }, [cotacaoId]);

  useEffect(() => {
    void load();
  }, [load]);

  const updateDraft = (participanteId: number, itemId: number, patch: Partial<RespostaDraft>) => {
    const key = `${participanteId}-${itemId}`;
    setDrafts((current) => ({ ...current, [key]: { ...(current[key] || emptyDraft()), ...patch } }));
  };

  const registrarResposta = async (participanteId: number, itemId: number) => {
    if (!cotacao) return;
    const key = `${participanteId}-${itemId}`;
    const draft = drafts[key] || emptyDraft();
    setSavingKey(key);
    setError('');
    try {
      await cotacoesFornecedoresService.resposta(cotacao.id, {
        participante_id: participanteId,
        cotacao_item_id: itemId,
        preco_unitario: draft.status_item === 'RESPONDIDO' ? Number(draft.preco_unitario || 0) : null,
        preco_unitario_bruto: draft.preco_unitario_bruto ? Number(draft.preco_unitario_bruto) : null,
        desconto: draft.desconto ? Number(draft.desconto) : null,
        quantidade_atendida: Number(draft.quantidade_atendida || 0),
        unidade_cotada: draft.unidade_cotada,
        fator_conversao: draft.fator_conversao ? Number(draft.fator_conversao) : null,
        prazo_entrega: draft.prazo_entrega,
        frete: draft.frete ? Number(draft.frete) : null,
        frete_tipo: draft.frete_tipo,
        frete_tipo_codigo: draft.frete_tipo,
        ipi_custo: draft.ipi_custo ? Number(draft.ipi_custo) : null,
        icms_st_custo: draft.icms_st_custo ? Number(draft.icms_st_custo) : null,
        outros_tributos_custo: draft.outros_tributos_custo ? Number(draft.outros_tributos_custo) : null,
        despesas_adicionais: draft.despesas_adicionais ? Number(draft.despesas_adicionais) : null,
        status_item: draft.status_item,
      });
      setDrafts((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, { fallback: 'Não foi possível registrar a resposta.' }));
    } finally {
      setSavingKey('');
    }
  };

  const selecionarReferencia = async (respostaId: number) => {
    if (!cotacao) return;
    setSavingKey(`select-${respostaId}`);
    setError('');
    try {
      await cotacoesFornecedoresService.selecionarReferencia(cotacao.id, respostaId);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, { fallback: 'Não foi possível selecionar a referência.' }));
    } finally {
      setSavingKey('');
    }
  };

  if (loading) return <div className="py-12 text-center text-sm text-muted-foreground">Carregando cotação…</div>;
  if (!cotacao || !comparativo) return <ErrorState message={error || 'Cotação não encontrada.'} onRetry={() => void load()} />;

  const totalRespostas = comparativo.itens.reduce((total, item) => total + item.respostas.length, 0);

  return (
    <div className="min-w-0">
      <PageHeader
        title={cotacao.numero}
        description="Consulte os dados da cotação, registre respostas e compare o custo efetivo das ofertas."
        breadcrumbs={[
          { label: 'Compras' },
          { label: 'Cotações com Fornecedores', path: '/cotacoes-fornecedores' },
          { label: cotacao.numero },
        ]}
        badges={<StatusBadge status={cotacao.status} label={labelStatusCotacao(cotacao.status)} />}
        actions={(
          <div className="flex flex-wrap gap-2">
            <button type="button" className="erp-btn-outline" onClick={() => navigate('/cotacoes-fornecedores')}>
              <ArrowLeft className="h-4 w-4" /> Voltar
            </button>
            <button type="button" className="erp-btn-outline" onClick={() => void load()}>
              <RefreshCw className="h-4 w-4" /> Atualizar
            </button>
          </div>
        )}
      />

      {error ? <div className="erp-alert erp-alert-error mb-4">{error}</div> : null}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="min-w-0">
        <TabsList className="mb-4 flex h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap p-1">
          <TabsTrigger value="resumo" onClick={() => setActiveTab('resumo')}>Resumo</TabsTrigger>
          <TabsTrigger value="itens" onClick={() => setActiveTab('itens')}>Itens</TabsTrigger>
          <TabsTrigger value="fornecedores" onClick={() => setActiveTab('fornecedores')}>Fornecedores</TabsTrigger>
          <TabsTrigger value="respostas" onClick={() => setActiveTab('respostas')}>Respostas</TabsTrigger>
          <TabsTrigger value="comparativo" onClick={() => setActiveTab('comparativo')}>Comparativo</TabsTrigger>
          <TabsTrigger value="historico" onClick={() => setActiveTab('historico')}>Histórico</TabsTrigger>
        </TabsList>

        <TabsContent value="resumo" className="mt-0 space-y-4">
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="erp-card p-4"><p className="text-xs text-muted-foreground">Origem</p><p className="mt-1 font-semibold">{labelOrigemCotacao(cotacao)}</p></div>
            <div className="erp-card p-4"><p className="text-xs text-muted-foreground">Proposta</p><p className="mt-1 font-semibold">{cotacao.proposta_id == null ? '—' : <Link className="text-primary hover:underline" to={`/propostas?proposta_id=${cotacao.proposta_id}`}>#{cotacao.proposta_id}</Link>}</p></div>
            <div className="erp-card p-4"><p className="text-xs text-muted-foreground">Itens</p><p className="mt-1 text-xl font-semibold">{cotacao.itens.length}</p></div>
            <div className="erp-card p-4"><p className="text-xs text-muted-foreground">Fornecedores</p><p className="mt-1 text-xl font-semibold">{cotacao.participantes.length}</p></div>
          </section>
          <section className="erp-card p-4 sm:p-5">
            <dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
              <div><dt className="text-xs text-muted-foreground">Responsável</dt><dd className="mt-1 font-medium">{cotacao.responsavel_nome || '—'}</dd></div>
              <div><dt className="text-xs text-muted-foreground">Data</dt><dd className="mt-1 font-medium">{formatDateBr(cotacao.data) || '—'}</dd></div>
              <div><dt className="text-xs text-muted-foreground">Prazo de resposta</dt><dd className="mt-1 font-medium">{formatDateBr(cotacao.prazo_resposta) || '—'}</dd></div>
              <div><dt className="text-xs text-muted-foreground">Última atualização</dt><dd className="mt-1 font-medium">{formatDateTime(cotacao.atualizado_em)}</dd></div>
            </dl>
            {cotacao.observacao ? <div className="mt-5 border-t border-border pt-4"><p className="text-xs text-muted-foreground">Observação</p><p className="mt-1 whitespace-pre-wrap text-sm">{cotacao.observacao}</p></div> : null}
          </section>
        </TabsContent>

        <TabsContent value="itens" className="mt-0">
          <DataTableShell>
            <DataTable>
              <thead><tr><th>Descrição</th><th>Quantidade</th><th>Unidade</th><th>Produto</th><th>Status</th></tr></thead>
              <tbody>
                {cotacao.itens.map((item) => (
                  <tr key={item.id}>
                    <td className="font-medium">{descricaoItemCotacao(item)}</td>
                    <td>{item.quantidade}</td>
                    <td>{item.unidade || '—'}</td>
                    <td>{item.produto_nome || '—'}</td>
                    <td><StatusBadge status={item.status} label={labelStatusCotacao(item.status)} /></td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </DataTableShell>
        </TabsContent>

        <TabsContent value="fornecedores" className="mt-0">
          <DataTableShell>
            <DataTable>
              <thead><tr><th>Fornecedor</th><th>Status</th><th>Enviado em</th><th>Respondido em</th><th>Respostas</th></tr></thead>
              <tbody>
                {cotacao.participantes.map((participante) => (
                  <tr key={participante.id}>
                    <td className="font-medium">{participante.fornecedor_nome}</td>
                    <td><StatusBadge status={participante.status} label={labelStatusCotacao(participante.status)} /></td>
                    <td>{formatDateTime(participante.enviado_em)}</td>
                    <td>{formatDateTime(participante.respondido_em)}</td>
                    <td>{participante.respostas.length}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </DataTableShell>
        </TabsContent>

        <TabsContent value="respostas" className="mt-0 space-y-4">
          {comparativo.itens.length === 0 || cotacao.participantes.length === 0 ? (
            <EmptyState message="Adicione itens e fornecedores para registrar respostas." />
          ) : comparativo.itens.map((item) => (
            <section key={item.cotacao_item_id} className="erp-card min-w-0 space-y-4 p-4 sm:p-5">
              <div>
                <h3 className="font-semibold">{item.descricao || `Item #${item.cotacao_item_id}`}</h3>
                <p className="text-xs text-muted-foreground">Quantidade {item.quantidade} {item.unidade}</p>
              </div>
              <div className="grid min-w-0 gap-3 xl:grid-cols-2">
                {cotacao.participantes.map((participante) => {
                  const resposta = item.respostas.find((row) => row.participante === participante.id);
                  const key = `${participante.id}-${item.cotacao_item_id}`;
                  const draft = drafts[key] || emptyDraft();
                  return (
                    <article key={participante.id} className="min-w-0 rounded-lg border border-border bg-muted/10 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="truncate font-semibold">{participante.fornecedor_nome}</h4>
                        <StatusBadge status={resposta?.status_item || participante.status} label={labelStatusCotacao(resposta?.status_item || participante.status)} />
                      </div>
                      {resposta ? (
                        <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                          <p><span className="text-muted-foreground">Preço:</span> {money(resposta.preco_unitario)}</p>
                          <p><span className="text-muted-foreground">Atendida:</span> {resposta.quantidade_atendida} {resposta.unidade_cotada || item.unidade}</p>
                          <p><span className="text-muted-foreground">Prazo:</span> {resposta.prazo_entrega || '—'}</p>
                          <p><span className="text-muted-foreground">Frete:</span> {money(resposta.frete)} {resposta.frete_tipo_codigo || resposta.frete_tipo}</p>
                        </div>
                      ) : (
                        <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2">
                          <p className="text-xs font-semibold uppercase text-muted-foreground sm:col-span-2">Oferta</p>
                          <input aria-label={`Preço líquido de ${participante.fornecedor_nome}`} className="erp-input min-w-0" placeholder="Preço unitário líquido" value={draft.preco_unitario} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { preco_unitario: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Preço bruto (opcional)" value={draft.preco_unitario_bruto} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { preco_unitario_bruto: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Desconto (opcional)" value={draft.desconto} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { desconto: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Qtd. atendida" value={draft.quantidade_atendida} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { quantidade_atendida: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Unidade cotada" value={draft.unidade_cotada} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { unidade_cotada: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Fator conversão (opcional)" value={draft.fator_conversao} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { fator_conversao: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Prazo" value={draft.prazo_entrega} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { prazo_entrega: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Frete" value={draft.frete} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { frete: event.target.value })} />
                          <select aria-label={`Tipo de frete de ${participante.fornecedor_nome}`} className="erp-input min-w-0" value={draft.frete_tipo} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { frete_tipo: event.target.value })}>
                            <option value="">Tipo de frete</option><option value="CIF">CIF</option><option value="FOB">FOB</option><option value="INCLUSO">Incluso</option><option value="OUTRO">Outro</option>
                          </select>
                          <p className="text-xs font-semibold uppercase text-muted-foreground sm:col-span-2">Tributos e custos</p>
                          <input className="erp-input min-w-0" placeholder="IPI de custo" value={draft.ipi_custo} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { ipi_custo: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="ICMS-ST de custo" value={draft.icms_st_custo} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { icms_st_custo: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Outros tributos" value={draft.outros_tributos_custo} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { outros_tributos_custo: event.target.value })} />
                          <input className="erp-input min-w-0" placeholder="Despesas adicionais" value={draft.despesas_adicionais} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { despesas_adicionais: event.target.value })} />
                          <select aria-label={`Status da resposta de ${participante.fornecedor_nome}`} className="erp-input min-w-0" value={draft.status_item} onChange={(event) => updateDraft(participante.id, item.cotacao_item_id, { status_item: event.target.value })}>
                            <option value="RESPONDIDO">Respondido</option><option value="RECUSADO">Recusado</option><option value="SEM_RETORNO">Sem retorno</option>
                          </select>
                          <button type="button" className="erp-btn-primary" disabled={savingKey === key} onClick={() => void registrarResposta(participante.id, item.cotacao_item_id)}>
                            <Send className="h-4 w-4" /> {savingKey === key ? 'Registrando…' : 'Registrar'}
                          </button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </TabsContent>

        <TabsContent value="comparativo" className="mt-0 space-y-4">
          {totalRespostas === 0 ? (
            <EmptyState message="Nenhuma resposta registrada para comparar." />
          ) : comparativo.itens.map((item) => (
            <section key={item.cotacao_item_id} className="erp-card min-w-0 space-y-4 p-4 sm:p-5">
              <div>
                <h3 className="font-semibold">{item.descricao || `Item #${item.cotacao_item_id}`}</h3>
                <p className="text-xs text-muted-foreground">Quantidade {item.quantidade} {item.unidade}</p>
              </div>
              {item.respostas.length ? (
                <div className="grid min-w-0 gap-3 xl:grid-cols-2">
                  {item.respostas.map((resposta) => (
                    <RespostaEconomica
                      key={resposta.id}
                      resposta={resposta}
                      item={item}
                      selecting={savingKey === `select-${resposta.id}`}
                      onSelect={(respostaId) => void selecionarReferencia(respostaId)}
                    />
                  ))}
                </div>
              ) : <p className="text-sm text-muted-foreground">Sem respostas para este item.</p>}
            </section>
          ))}
        </TabsContent>

        <TabsContent value="historico" className="mt-0">
          <section className="erp-card p-4 sm:p-5">
            {historico.length ? (
              <ol className="space-y-0">
                {historico.map((evento, index) => (
                  <li key={evento.id} className="relative grid gap-1 border-l border-border pb-5 pl-5 last:pb-0">
                    <span className="absolute -left-1.5 top-1 h-3 w-3 rounded-full border-2 border-background bg-primary" />
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-sm font-semibold">{evento.descricao || evento.evento}</p>
                      <time className="text-xs text-muted-foreground">{formatDateTime(evento.criado_em)}</time>
                    </div>
                    <p className="text-xs text-muted-foreground">{evento.usuario_nome || 'Sistema'}{index === 0 ? ' · evento mais recente' : ''}</p>
                  </li>
                ))}
              </ol>
            ) : <EmptyState message="Nenhum evento registrado no histórico." />}
          </section>
        </TabsContent>
      </Tabs>
    </div>
  );
}
