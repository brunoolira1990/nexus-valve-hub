import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, ExternalLink, Plus, Search, Trash2, X } from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { apiErrorMessage } from '@/services/api/config';
import { cotacoesFornecedoresService, propostasService } from '@/services/api/comercial';
import { fornecedoresService } from '@/services/api/fornecedores';
import { produtosService } from '@/services/api/produtos';
import type { Fornecedor, Produto, Proposta } from '@/types';

type ModoCotacao = 'proposta' | 'manual';
type ItemManualDraft = {
  key: number;
  descricao_item: string;
  unidade: string;
  quantidade: string;
  produto_id: string;
};

const novoItemManual = (key: number): ItemManualDraft => ({
  key,
  descricao_item: '',
  unidade: '',
  quantidade: '',
  produto_id: '',
});

const itemManualValido = (item: ItemManualDraft) =>
  Boolean(item.descricao_item.trim() && item.unidade.trim() && Number(item.quantidade) > 0);

export default function CotacaoFornecedorNova() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const propostaInicial = Number(params.get('proposta_id') || 0) || null;
  const [modo, setModo] = useState<ModoCotacao>(propostaInicial ? 'proposta' : 'manual');
  const [propostas, setPropostas] = useState<Proposta[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [propostaId, setPropostaId] = useState<number | null>(propostaInicial);
  const [itensSelecionados, setItensSelecionados] = useState<number[]>([]);
  const [itensManuais, setItensManuais] = useState<ItemManualDraft[]>([novoItemManual(1)]);
  const [nextManualKey, setNextManualKey] = useState(2);
  const [fornecedoresSelecionados, setFornecedoresSelecionados] = useState<number[]>([]);
  const [buscaFornecedor, setBuscaFornecedor] = useState('');
  const [buscaItemProposta, setBuscaItemProposta] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const [propostasRows, fornecedoresRows, produtosRows] = await Promise.all([
          propostasService.getAll({ limit: 200 }),
          fornecedoresService.getAll({ limit: 500 }),
          produtosService.getAll({ limit: 200 }),
        ]);
        if (!active) return;
        setPropostas(propostasRows);
        setFornecedores(fornecedoresRows.filter((fornecedor) => fornecedor.ativo));
        setProdutos(produtosRows.filter((produto) => produto.ativo));
      } catch (err) {
        if (active) {
          setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar os dados da nova cotação.' }));
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const propostaAtual = useMemo(
    () => propostas.find((proposta) => proposta.id === propostaId) || null,
    [propostaId, propostas],
  );

  const fornecedoresSelecionadosRows = useMemo(
    () => fornecedores.filter((fornecedor) => fornecedoresSelecionados.includes(fornecedor.id)),
    [fornecedores, fornecedoresSelecionados],
  );

  const fornecedoresVisiveis = useMemo(() => {
    const termo = buscaFornecedor.trim().toLocaleLowerCase('pt-BR');
    if (!termo) return fornecedores;
    return fornecedores.filter((fornecedor) =>
      [fornecedor.razao_social, fornecedor.nome_fantasia, fornecedor.cnpj]
        .join(' ')
        .toLocaleLowerCase('pt-BR')
        .includes(termo),
    );
  }, [buscaFornecedor, fornecedores]);

  const itensPropostaVisiveis = useMemo(() => {
    const rows = propostaAtual?.itens || [];
    const termo = buscaItemProposta.trim().toLocaleLowerCase('pt-BR');
    if (!termo) return rows;
    return rows.filter((item) =>
      [item.produto_nome, item.descricao_avulsa, item.unidade_negociada]
        .join(' ')
        .toLocaleLowerCase('pt-BR')
        .includes(termo),
    );
  }, [buscaItemProposta, propostaAtual]);

  const itensManuaisValidos = useMemo(() => itensManuais.filter(itemManualValido), [itensManuais]);
  const itensManuaisCompletos = itensManuais.length > 0 && itensManuaisValidos.length === itensManuais.length;
  const quantidadeItens = modo === 'proposta' ? itensSelecionados.length : itensManuaisValidos.length;
  const itensProntos = modo === 'proposta'
    ? Boolean(propostaId && itensSelecionados.length)
    : itensManuaisCompletos;
  const fornecedoresProntos = fornecedoresSelecionados.length > 0;
  const prontaParaCriar = itensProntos && fornecedoresProntos;

  const updateManual = (key: number, patch: Partial<ItemManualDraft>) => {
    setItensManuais((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  };

  const adicionarManual = () => {
    setItensManuais((current) => [...current, novoItemManual(nextManualKey)]);
    setNextManualKey((current) => current + 1);
  };

  const removerManual = (key: number) => {
    setItensManuais((current) => current.filter((item) => item.key !== key));
  };

  const toggleFornecedor = (fornecedorId: number) => {
    setFornecedoresSelecionados((current) =>
      current.includes(fornecedorId)
        ? current.filter((id) => id !== fornecedorId)
        : [...current, fornecedorId],
    );
  };

  const criarCotacao = async () => {
    if (!prontaParaCriar) return;
    setSaving(true);
    setError('');
    try {
      const nova = await cotacoesFornecedoresService.create({
        proposta: modo === 'proposta' ? propostaId : null,
        observacao: modo === 'manual' ? 'Cotação manual.' : 'Cotação criada a partir da Proposta.',
      });
      if (modo === 'proposta') {
        for (const itemId of itensSelecionados) {
          await cotacoesFornecedoresService.addItem(nova.id, { item_proposta_id: itemId });
        }
      } else {
        for (const item of itensManuaisValidos) {
          await cotacoesFornecedoresService.addItem(nova.id, {
            descricao_item: item.descricao_item.trim(),
            unidade: item.unidade.trim(),
            quantidade: Number(item.quantidade),
            ...(item.produto_id ? { produto_id: Number(item.produto_id) } : {}),
          });
        }
      }
      for (const fornecedorId of fornecedoresSelecionados) {
        await cotacoesFornecedoresService.addParticipante(nova.id, fornecedorId);
      }
      navigate(`/cotacoes-fornecedores/${nova.id}`);
    } catch (err) {
      setError(apiErrorMessage(err, { fallback: 'Não foi possível criar a cotação.' }));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="py-12 text-center text-sm text-muted-foreground">Carregando nova cotação…</div>;
  if (error && !propostas.length && !fornecedores.length) {
    return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="Nova cotação"
        description="Defina os itens e fornecedores que participarão da consulta."
        breadcrumbs={[
          { label: 'Compras' },
          { label: 'Cotações com Fornecedores', path: '/cotacoes-fornecedores' },
          { label: 'Nova cotação' },
        ]}
        actions={(
          <button type="button" className="erp-btn-outline" onClick={() => navigate('/cotacoes-fornecedores')}>
            Voltar à listagem
          </button>
        )}
      />

      {error ? <div className="erp-alert erp-alert-error mb-4">{error}</div> : null}

      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="min-w-0 space-y-5">
          <section className="erp-card space-y-4 p-4 sm:p-5">
            <div>
              <h2 className="text-base font-semibold">Origem da cotação</h2>
              <p className="mt-1 text-sm text-muted-foreground">Escolha como os itens serão informados.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className={`cursor-pointer rounded-lg border p-4 transition-colors ${modo === 'manual' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                <div className="flex items-start gap-3">
                  <input
                    type="radio"
                    name="modo-cotacao"
                    value="manual"
                    checked={modo === 'manual'}
                    onChange={() => setModo('manual')}
                    className="mt-1"
                  />
                  <span>
                    <span className="block font-medium">Manual</span>
                    <span className="mt-1 block text-xs text-muted-foreground">Informe livremente descrição, unidade e quantidade.</span>
                  </span>
                </div>
              </label>
              <label className={`cursor-pointer rounded-lg border p-4 transition-colors ${modo === 'proposta' ? 'border-primary bg-primary/5' : 'border-border'}`}>
                <div className="flex items-start gap-3">
                  <input
                    type="radio"
                    name="modo-cotacao"
                    value="proposta"
                    checked={modo === 'proposta'}
                    onChange={() => setModo('proposta')}
                    className="mt-1"
                  />
                  <span>
                    <span className="block font-medium">Vinculada à Proposta</span>
                    <span className="mt-1 block text-xs text-muted-foreground">Selecione os itens diretamente de uma Proposta.</span>
                  </span>
                </div>
              </label>
            </div>
          </section>

          {modo === 'manual' ? (
            <section className="erp-card space-y-4 p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold">Itens da cotação</h2>
                  <p className="mt-1 text-sm text-muted-foreground">O produto catalogado é opcional.</p>
                </div>
                <button type="button" className="erp-btn-outline erp-btn-sm self-start" onClick={adicionarManual}>
                  <Plus className="h-4 w-4" />
                  Adicionar item
                </button>
              </div>

              {itensManuais.length === 0 ? (
                <EmptyState
                  message="Nenhum item adicionado."
                  actionLabel="Adicionar item"
                  onAction={adicionarManual}
                />
              ) : (
                <div className="space-y-3">
                  {itensManuais.map((item, index) => (
                    <article key={item.key} className="rounded-lg border border-border bg-muted/10 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold">Item {index + 1}</h3>
                        <button
                          type="button"
                          className="erp-btn-ghost erp-btn-sm text-destructive"
                          aria-label={`Remover item ${index + 1}`}
                          onClick={() => removerManual(item.key)}
                        >
                          <Trash2 className="h-4 w-4" />
                          Remover
                        </button>
                      </div>
                      <label className="block text-xs font-medium text-muted-foreground">
                        Descrição técnica
                        <textarea
                          className="erp-input mt-1 min-h-20 w-full resize-y"
                          placeholder="Descreva o item que será cotado"
                          value={item.descricao_item}
                          onChange={(event) => updateManual(item.key, { descricao_item: event.target.value })}
                        />
                      </label>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-[8rem_10rem_minmax(0,1fr)]">
                        <label className="min-w-0 text-xs font-medium text-muted-foreground">
                          Unidade
                          <input
                            className="erp-input mt-1 w-full"
                            placeholder="Ex.: PC"
                            value={item.unidade}
                            onChange={(event) => updateManual(item.key, { unidade: event.target.value })}
                          />
                        </label>
                        <label className="min-w-0 text-xs font-medium text-muted-foreground">
                          Quantidade
                          <input
                            className="erp-input mt-1 w-full"
                            type="number"
                            min="0.001"
                            step="0.001"
                            placeholder="0,000"
                            value={item.quantidade}
                            onChange={(event) => updateManual(item.key, { quantidade: event.target.value })}
                          />
                        </label>
                        <label className="min-w-0 text-xs font-medium text-muted-foreground sm:col-span-2 xl:col-span-1">
                          Produto catalogado opcional
                          <select
                            className="erp-input mt-1 w-full"
                            value={item.produto_id}
                            onChange={(event) => updateManual(item.key, { produto_id: event.target.value })}
                          >
                            <option value="">Nenhum produto vinculado</option>
                            {produtos.map((produto) => (
                              <option key={produto.id} value={produto.id}>
                                {produto.codigo_completo} — {produto.descricao}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          ) : (
            <section className="erp-card space-y-4 p-4 sm:p-5">
              <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <label className="min-w-0 text-sm font-medium">
                  Proposta
                  <select
                    aria-label="Selecionar Proposta"
                    className="erp-input mt-1 w-full"
                    value={propostaId || ''}
                    onChange={(event) => {
                      setPropostaId(Number(event.target.value) || null);
                      setItensSelecionados([]);
                      setBuscaItemProposta('');
                    }}
                  >
                    <option value="">Selecione uma Proposta</option>
                    {propostas.map((proposta) => (
                      <option key={proposta.id} value={proposta.id}>
                        {proposta.numero} — {proposta.cliente_nome || proposta.cliente_avulso_nome || 'Cliente avulso'}
                      </option>
                    ))}
                  </select>
                </label>
                <Link
                  className="erp-btn-outline inline-flex items-center justify-center gap-2"
                  to={propostaId ? `/propostas?proposta_id=${propostaId}` : '/propostas'}
                >
                  Abrir Proposta <ExternalLink className="h-4 w-4" />
                </Link>
              </div>

              {propostaAtual ? (
                <>
                  <div className="grid gap-3 rounded-lg border border-border bg-muted/20 p-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div><p className="text-xs text-muted-foreground">Número</p><p className="font-semibold">{propostaAtual.numero}</p></div>
                    <div><p className="text-xs text-muted-foreground">Cliente</p><p className="font-semibold">{propostaAtual.cliente_nome || propostaAtual.cliente_avulso_nome || 'Cliente avulso'}</p></div>
                    <div><p className="text-xs text-muted-foreground">Total de itens</p><p className="font-semibold">{propostaAtual.itens.length}</p></div>
                    <div><p className="text-xs text-muted-foreground">Selecionados</p><p className="font-semibold">{itensSelecionados.length}</p></div>
                  </div>

                  <label className="relative block">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                      aria-label="Buscar item da Proposta"
                      className="erp-input w-full pl-9"
                      placeholder="Buscar item da Proposta..."
                      value={buscaItemProposta}
                      onChange={(event) => setBuscaItemProposta(event.target.value)}
                    />
                  </label>

                  <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                    {itensPropostaVisiveis.map((item) => {
                      const quantidade = item.quantidade_negociada ?? item.quantidade;
                      const descricao = item.produto_nome || item.descricao_avulsa || `Item #${item.id}`;
                      return (
                        <label key={item.id} className="flex cursor-pointer items-start gap-3 p-3 hover:bg-muted/30 sm:items-center">
                          <input
                            type="checkbox"
                            className="mt-1 sm:mt-0"
                            checked={itensSelecionados.includes(item.id)}
                            onChange={(event) => setItensSelecionados((current) =>
                              event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id),
                            )}
                          />
                          <span className="min-w-0 flex-1 text-sm font-medium">{descricao}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {quantidade} {item.unidade_negociada || ''}
                          </span>
                        </label>
                      );
                    })}
                    {itensPropostaVisiveis.length === 0 ? (
                      <p className="p-4 text-center text-sm text-muted-foreground">Nenhum item encontrado.</p>
                    ) : null}
                  </div>
                </>
              ) : (
                <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  Selecione uma Proposta para visualizar seus itens.
                </p>
              )}
            </section>
          )}

          <section className="erp-card space-y-4 p-4 sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-semibold">Fornecedores</h2>
                <p className="mt-1 text-sm text-muted-foreground">{fornecedoresSelecionados.length} selecionados</p>
              </div>
              <label className="relative block w-full sm:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  aria-label="Buscar fornecedor"
                  className="erp-input w-full pl-9"
                  placeholder="Buscar fornecedor..."
                  value={buscaFornecedor}
                  onChange={(event) => setBuscaFornecedor(event.target.value)}
                />
              </label>
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Selecionados</h3>
              {fornecedoresSelecionadosRows.length ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {fornecedoresSelecionadosRows.map((fornecedor) => (
                    <span key={fornecedor.id} className="inline-flex max-w-full items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-sm">
                      <span className="truncate">{fornecedor.razao_social}</span>
                      <button
                        type="button"
                        aria-label={`Remover fornecedor ${fornecedor.razao_social}`}
                        className="shrink-0 text-muted-foreground hover:text-destructive"
                        onClick={() => toggleFornecedor(fornecedor.id)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">Nenhum fornecedor selecionado.</p>
              )}
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Todos os fornecedores</h3>
              <div className="mt-2 max-h-80 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                {fornecedoresVisiveis.map((fornecedor) => (
                  <label key={fornecedor.id} className="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-muted/30">
                    <input
                      type="checkbox"
                      checked={fornecedoresSelecionados.includes(fornecedor.id)}
                      onChange={() => toggleFornecedor(fornecedor.id)}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{fornecedor.razao_social}</span>
                      {fornecedor.cnpj ? <span className="block text-xs text-muted-foreground">{fornecedor.cnpj}</span> : null}
                    </span>
                  </label>
                ))}
                {fornecedoresVisiveis.length === 0 ? (
                  <p className="p-4 text-center text-sm text-muted-foreground">Nenhum fornecedor encontrado.</p>
                ) : null}
              </div>
            </div>
          </section>
        </div>

        <aside className="erp-card space-y-4 p-4 sm:p-5 lg:sticky lg:top-4">
          <div>
            <h2 className="text-base font-semibold">Resumo da nova cotação</h2>
            <p className="mt-1 text-sm text-muted-foreground">Confira o preenchimento antes de criar.</p>
          </div>
          <dl className="space-y-3 text-sm">
            <div className="flex items-start justify-between gap-3"><dt className="text-muted-foreground">Modo</dt><dd className="text-right font-medium">{modo === 'manual' ? 'Manual' : 'Vinculada à Proposta'}</dd></div>
            {modo === 'proposta' ? (
              <div className="flex items-start justify-between gap-3"><dt className="text-muted-foreground">Proposta</dt><dd className="text-right font-medium">{propostaAtual?.numero || 'Não selecionada'}</dd></div>
            ) : null}
            <div className="flex items-start justify-between gap-3"><dt className="text-muted-foreground">Itens selecionados</dt><dd className="font-medium">{quantidadeItens}</dd></div>
            <div className="flex items-start justify-between gap-3"><dt className="text-muted-foreground">Fornecedores</dt><dd className="font-medium">{fornecedoresSelecionados.length}</dd></div>
          </dl>

          <div className={`rounded-lg border p-3 text-sm ${prontaParaCriar ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-100' : 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100'}`}>
            <div className="flex items-start gap-2">
              {prontaParaCriar ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />}
              <div>
                <p className="font-semibold">{prontaParaCriar ? 'Pronta para criar' : 'Preenchimento pendente'}</p>
                {!itensProntos ? <p className="mt-1 text-xs">Selecione pelo menos um item.</p> : null}
                {!fornecedoresProntos ? <p className="mt-1 text-xs">Selecione pelo menos um fornecedor.</p> : null}
              </div>
            </div>
          </div>

          <button
            type="button"
            className="erp-btn-primary flex w-full items-center justify-center gap-2"
            disabled={saving || !prontaParaCriar}
            onClick={() => void criarCotacao()}
          >
            <Plus className="h-4 w-4" />
            {saving ? 'Criando cotação…' : 'Criar cotação'}
          </button>
        </aside>
      </div>
    </div>
  );
}
