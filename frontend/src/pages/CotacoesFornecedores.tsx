import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, RefreshCw, Send, CheckCircle2, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState, ErrorState } from '@/components/list/ListStates';
import { formatMoneyBRL } from '@/lib/numberFields';
import { cotacoesFornecedoresService, propostasService } from '@/services/api/comercial';
import { fornecedoresService } from '@/services/api/fornecedores';
import { produtosService } from '@/services/api/produtos';
import type { CotacaoComparativo, CotacaoFornecedor, Fornecedor, Produto, Proposta } from '@/types';

const statusLabel: Record<string, string> = {
  RASCUNHO: 'Rascunho', EM_COTACAO: 'Em cotação', PARCIAL: 'Parcial', CONCLUIDA: 'Concluída', CANCELADA: 'Cancelada',
  PENDENTE: 'Pendente', RESPONDIDO: 'Respondido', RECUSADO: 'Recusado', SEM_RETORNO: 'Sem retorno',
};

type ModoCotacao = 'proposta' | 'manual';
type RespostaDraft = { preco_unitario: string; quantidade_atendida: string; prazo_entrega: string; frete: string; frete_tipo: string; status_item: string };
type ItemManualDraft = { key: number; descricao_item: string; unidade: string; quantidade: string; produto_id: string };

export default function CotacoesFornecedores() {
  const [params] = useSearchParams();
  const propostaInicial = Number(params.get('proposta_id') || 0) || null;
  const [modo, setModo] = useState<ModoCotacao>(propostaInicial ? 'proposta' : 'manual');
  const [propostas, setPropostas] = useState<Proposta[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [propostaId, setPropostaId] = useState<number | null>(propostaInicial);
  const [cotacao, setCotacao] = useState<CotacaoFornecedor | null>(null);
  const [comparativo, setComparativo] = useState<CotacaoComparativo | null>(null);
  const [itensSelecionados, setItensSelecionados] = useState<number[]>([]);
  const [fornecedoresSelecionados, setFornecedoresSelecionados] = useState<number[]>([]);
  const [itensManuais, setItensManuais] = useState<ItemManualDraft[]>([{ key: 1, descricao_item: '', unidade: '', quantidade: '', produto_id: '' }]);
  const [nextManualKey, setNextManualKey] = useState(2);
  const [drafts, setDrafts] = useState<Record<string, RespostaDraft>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const propostaAtual = useMemo(() => propostas.find((p) => p.id === propostaId) || null, [propostas, propostaId]);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [ps, fs, prs] = await Promise.all([propostasService.getAll({ limit: 200 }), fornecedoresService.getAll({ limit: 200 }), produtosService.getAll({ limit: 200 })]);
      setPropostas(ps); setFornecedores(fs.filter((f) => f.ativo)); setProdutos(prs.filter((p) => p.ativo));
    } catch (err) { setError(err instanceof Error ? err.message : 'Não foi possível carregar Propostas, Fornecedores e Produtos.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const refreshCotacao = async (id: number) => {
    const [detail, compare] = await Promise.all([cotacoesFornecedoresService.getById(id), cotacoesFornecedoresService.comparativo(id)]);
    setCotacao(detail); setComparativo(compare);
  };

  const criarCotacao = async () => {
    const manuaisValidos = itensManuais.filter((item) => item.descricao_item.trim() && item.unidade.trim() && Number(item.quantidade) > 0);
    if (!fornecedoresSelecionados.length || (modo === 'proposta' && (!propostaId || !itensSelecionados.length)) || (modo === 'manual' && manuaisValidos.length !== itensManuais.length)) return;
    setSaving(true); setError('');
    try {
      const nova = await cotacoesFornecedoresService.create({ proposta: modo === 'proposta' ? propostaId : null, observacao: modo === 'manual' ? 'Cotação manual.' : 'Cotação criada a partir da Proposta.' });
      if (modo === 'proposta') for (const itemId of itensSelecionados) await cotacoesFornecedoresService.addItem(nova.id, { item_proposta_id: itemId });
      else for (const item of manuaisValidos) await cotacoesFornecedoresService.addItem(nova.id, { descricao_item: item.descricao_item.trim(), unidade: item.unidade.trim(), quantidade: Number(item.quantidade), ...(item.produto_id ? { produto_id: Number(item.produto_id) } : {}) });
      for (const fornecedorId of fornecedoresSelecionados) await cotacoesFornecedoresService.addParticipante(nova.id, fornecedorId);
      await refreshCotacao(nova.id);
    } catch (err) { setError(err instanceof Error ? err.message : 'Não foi possível criar a cotação.'); }
    finally { setSaving(false); }
  };

  const updateManual = (key: number, patch: Partial<ItemManualDraft>) => setItensManuais((prev) => prev.map((item) => item.key === key ? { ...item, ...patch } : item));
  const adicionarManual = () => { setItensManuais((prev) => [...prev, { key: nextManualKey, descricao_item: '', unidade: '', quantidade: '', produto_id: '' }]); setNextManualKey((value) => value + 1); };
  const removerManual = (key: number) => setItensManuais((prev) => prev.length === 1 ? prev : prev.filter((item) => item.key !== key));

  const registrarResposta = async (participanteId: number, itemId: number) => {
    if (!cotacao) return;
    const key = `${participanteId}-${itemId}`; const draft = drafts[key] || { preco_unitario: '', quantidade_atendida: '', prazo_entrega: '', frete: '', frete_tipo: '', status_item: 'RESPONDIDO' };
    setSaving(true);
    try { await cotacoesFornecedoresService.resposta(cotacao.id, { participante_id: participanteId, cotacao_item_id: itemId, preco_unitario: draft.status_item === 'RESPONDIDO' ? Number(draft.preco_unitario || 0) : null, quantidade_atendida: Number(draft.quantidade_atendida || 0), prazo_entrega: draft.prazo_entrega, frete: draft.frete ? Number(draft.frete) : null, frete_tipo: draft.frete_tipo, status_item: draft.status_item }); await refreshCotacao(cotacao.id); }
    catch (err) { setError(err instanceof Error ? err.message : 'Não foi possível registrar a resposta.'); } finally { setSaving(false); }
  };
  const updateDraft = (participanteId: number, itemId: number, patch: Partial<RespostaDraft>) => { const key = `${participanteId}-${itemId}`; setDrafts((prev) => ({ ...prev, [key]: { ...(prev[key] || { preco_unitario: '', quantidade_atendida: '', prazo_entrega: '', frete: '', frete_tipo: '', status_item: 'RESPONDIDO' }), ...patch } })); };

  if (loading) return <div className="p-6">Carregando Cotações com Fornecedores…</div>;
  if (error && !propostas.length && !fornecedores.length) return <ErrorState title="Falha ao carregar cotações" description={error} onRetry={() => void load()} />;

  return <div className="space-y-5">
    <PageHeader title="Cotações com Fornecedores" description="Consulte o mercado antes da formação de preço da Proposta, sem alterar custo ou preço de venda." actions={<button className="erp-btn-outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />Atualizar</button>} />
    {error && <div className="erp-alert erp-alert-error">{error}</div>}
    <section className="erp-card p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[220px] text-sm font-medium">Modo de cotação<select className="erp-input mt-1 w-full" value={modo} onChange={(e) => { setModo(e.target.value as ModoCotacao); setCotacao(null); setComparativo(null); }}><option value="proposta">Vinculada à Proposta</option><option value="manual">Cotação manual</option></select></label>
        {modo === 'proposta' && <><label className="min-w-[280px] flex-1 text-sm font-medium">Proposta<select className="erp-input mt-1 w-full" value={propostaId || ''} onChange={(e) => { setPropostaId(Number(e.target.value) || null); setCotacao(null); setComparativo(null); }}><option value="">Selecione uma Proposta</option>{propostas.map((p) => <option key={p.id} value={p.id}>{p.numero} — {p.cliente_nome || p.cliente_avulso_nome || 'Cliente avulso'}</option>)}</select></label><Link className="erp-btn-outline" to={propostaId ? `/propostas?proposta_id=${propostaId}` : '/propostas'}>Abrir Proposta</Link></>}
      </div>
      {!cotacao && modo === 'proposta' && propostaAtual && <div><h2 className="text-sm font-semibold">Itens para consultar</h2><div className="mt-2 grid gap-2 md:grid-cols-2">{(propostaAtual.itens || []).map((item) => <label key={item.id} className="flex items-center gap-2 rounded border p-2 text-sm"><input type="checkbox" checked={itensSelecionados.includes(item.id)} onChange={(e) => setItensSelecionados((prev) => e.target.checked ? [...prev, item.id] : prev.filter((id) => id !== item.id))} /><span>{item.produto_nome || item.descricao_avulsa || `Item #${item.id}`} · qtd. {item.quantidade_negociada || item.quantidade}</span></label>)}</div></div>}
      {!cotacao && modo === 'manual' && <div><div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Itens manuais</h2><button className="erp-btn-outline erp-btn-sm" onClick={adicionarManual}><Plus className="mr-1 h-4 w-4" />Adicionar item</button></div><div className="mt-2 space-y-2">{itensManuais.map((item) => <div key={item.key} className="grid gap-2 rounded border p-3 md:grid-cols-[2fr_120px_120px_2fr_auto]"><input className="erp-input" placeholder="Descrição técnica" value={item.descricao_item} onChange={(e) => updateManual(item.key, { descricao_item: e.target.value })} /><input className="erp-input" placeholder="Unidade" value={item.unidade} onChange={(e) => updateManual(item.key, { unidade: e.target.value })} /><input className="erp-input" type="number" min="0.001" step="0.001" placeholder="Quantidade" value={item.quantidade} onChange={(e) => updateManual(item.key, { quantidade: e.target.value })} /><select className="erp-input" value={item.produto_id} onChange={(e) => updateManual(item.key, { produto_id: e.target.value })}><option value="">Produto catalogado (opcional)</option>{produtos.map((p) => <option key={p.id} value={p.id}>{p.codigo_completo} — {p.descricao}</option>)}</select><button className="erp-btn-outline erp-btn-sm" title="Remover item" onClick={() => removerManual(item.key)}><Trash2 className="h-4 w-4" /></button></div>)}</div></div>}
      {!cotacao && <><div><h2 className="text-sm font-semibold">Fornecedores participantes</h2><div className="mt-2 grid gap-2 md:grid-cols-3">{fornecedores.map((f) => <label key={f.id} className="flex items-center gap-2 rounded border p-2 text-sm"><input type="checkbox" checked={fornecedoresSelecionados.includes(f.id)} onChange={(e) => setFornecedoresSelecionados((prev) => e.target.checked ? [...prev, f.id] : prev.filter((id) => id !== f.id))} /><span>{f.razao_social}</span></label>)}</div></div><button className="erp-btn-primary" disabled={saving || !fornecedoresSelecionados.length || (modo === 'proposta' ? !itensSelecionados.length || !propostaId : itensManuais.some((item) => !item.descricao_item.trim() || !item.unidade.trim() || Number(item.quantidade) <= 0))} onClick={() => void criarCotacao()}><Plus className="mr-2 h-4 w-4" />Criar cotação</button></>}
    </section>
    {cotacao && comparativo && <section className="erp-card p-4 space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">{cotacao.numero}</h2><p className="text-sm text-muted-foreground">Status: {statusLabel[cotacao.status] || cotacao.status} · referência apenas informativa</p></div><button className="erp-btn-outline" onClick={() => void refreshCotacao(cotacao.id)}><RefreshCw className="mr-2 h-4 w-4" />Recarregar comparativo</button></div>{comparativo.itens.length === 0 ? <EmptyState title="Nenhum item na cotação" description="Adicione itens para iniciar a consulta." /> : comparativo.itens.map((item) => <div key={item.cotacao_item_id} className="rounded border p-3"><h3 className="font-semibold">{item.descricao || `Item #${item.cotacao_item_id}`} · {item.unidade || 'un.'} · qtd. {item.quantidade}</h3><div className="mt-3 grid gap-3 xl:grid-cols-2">{cotacao.participantes.map((participante) => { const resposta = item.respostas.find((r) => r.participante === participante.id); const key = `${participante.id}-${item.cotacao_item_id}`; const draft = drafts[key] || { preco_unitario: '', quantidade_atendida: '', prazo_entrega: '', frete: '', frete_tipo: '', status_item: 'RESPONDIDO' }; return <div key={participante.id} className="rounded bg-muted/30 p-3"><div className="flex items-center justify-between"><strong>{participante.fornecedor_nome}</strong><span className="text-xs">{statusLabel[resposta?.status_item || participante.status] || participante.status}</span></div>{resposta ? <div className="mt-2 space-y-1 text-sm"><div>Preço: {resposta.preco_unitario == null ? '—' : formatMoneyBRL(resposta.preco_unitario)} · Atendida: {resposta.quantidade_atendida}</div><div>Prazo: {resposta.prazo_entrega || '—'} · Frete: {resposta.frete == null ? '—' : formatMoneyBRL(resposta.frete)} {resposta.frete_tipo}</div><div className="flex flex-wrap items-center gap-2">{resposta.selecionada_como_referencia && <span className="text-primary"><CheckCircle2 className="mr-1 inline h-4 w-4" />Referência selecionada</span>}<button className="erp-btn-outline erp-btn-sm" onClick={() => void cotacoesFornecedoresService.selecionarReferencia(cotacao.id, resposta.id).then(() => refreshCotacao(cotacao.id))}>Usar como referência</button></div></div> : <div className="mt-2 grid gap-2 sm:grid-cols-2"><input className="erp-input" placeholder="Preço unitário" value={draft.preco_unitario} onChange={(e) => updateDraft(participante.id, item.cotacao_item_id, { preco_unitario: e.target.value })} /><input className="erp-input" placeholder="Qtd. atendida" value={draft.quantidade_atendida} onChange={(e) => updateDraft(participante.id, item.cotacao_item_id, { quantidade_atendida: e.target.value })} /><input className="erp-input" placeholder="Prazo" value={draft.prazo_entrega} onChange={(e) => updateDraft(participante.id, item.cotacao_item_id, { prazo_entrega: e.target.value })} /><input className="erp-input" placeholder="Frete" value={draft.frete} onChange={(e) => updateDraft(participante.id, item.cotacao_item_id, { frete: e.target.value })} /><select className="erp-input" value={draft.status_item} onChange={(e) => updateDraft(participante.id, item.cotacao_item_id, { status_item: e.target.value })}><option value="RESPONDIDO">Respondido</option><option value="RECUSADO">Recusado</option><option value="SEM_RETORNO">Sem retorno</option></select><button className="erp-btn-primary" disabled={saving} onClick={() => void registrarResposta(participante.id, item.cotacao_item_id)}><Send className="mr-2 inline h-4 w-4" />Registrar</button></div>}</div>; })}</div></div>)}</section>}
  </div>;
}
