import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import {
  AVISO_COMPOSICAO_SEM_ESTOQUE,
  labelTipoComposicao,
} from '@/lib/conferenciaEquivalencia';
import {
  createProdutoComposicao,
  deleteProdutoComposicao,
  listProdutoComposicoes,
  type ProdutoComposicao,
  type ProdutoComposicaoItem,
  updateProdutoComposicao,
} from '@/services/api/produtoComposicao';

const TIPOS_COMPOSICAO = [
  'KIT_COMERCIAL',
  'MONTAGEM_SIMPLES',
  'MONTAGEM_ROSCADA',
  'MONTAGEM_SOLDADA',
  'MONTAGEM_SERVICO_INTERNO',
  'MONTAGEM_TERCEIRIZADA',
  'BENEFICIAMENTO',
] as const;

type Props = {
  produtoId: number;
  produtosOpcoes: Array<{ id: number; codigo_completo: string; descricao: string }>;
};

const emptyItem = (): ProdutoComposicaoItem => ({
  componente_produto_id: 0,
  quantidade_por_unidade_final: '1',
  obrigatorio: true,
  ordem: 0,
});

export function ProdutoComposicaoPanel({ produtoId, produtosOpcoes }: Props) {
  const [lista, setLista] = useState<ProdutoComposicao[]>([]);
  const [loading, setLoading] = useState(false);
  const [editando, setEditando] = useState<ProdutoComposicao | null>(null);
  const [erro, setErro] = useState('');

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listProdutoComposicoes(produtoId);
      setLista(data);
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro ao carregar composições.');
    } finally {
      setLoading(false);
    }
  }, [produtoId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const novaComposicao = () => {
    setEditando({
      produto_final_id: produtoId,
      nome: '',
      tipo_composicao: 'MONTAGEM_SIMPLES',
      ativo: true,
      padrao: lista.length === 0,
      permite_alternativa: true,
      permite_comprar_pronto: true,
      permite_montar: true,
      exige_confirmacao: true,
      exige_servico: false,
      itens: [emptyItem()],
    });
    setErro('');
  };

  const salvar = async () => {
    if (!editando) return;
    setErro('');
    try {
      const payload = {
        ...editando,
        itens: (editando.itens || []).filter((i) => i.componente_produto_id > 0),
      };
      if (payload.itens.length === 0) {
        setErro('Adicione ao menos um componente.');
        return;
      }
      if (editando.id) {
        await updateProdutoComposicao(editando.id, payload);
      } else {
        await createProdutoComposicao(payload);
      }
      setEditando(null);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro ao salvar composição.');
    }
  };

  const inativar = async (comp: ProdutoComposicao) => {
    if (!comp.id) return;
    await updateProdutoComposicao(comp.id, { ativo: false });
    await carregar();
  };

  const excluir = async (comp: ProdutoComposicao) => {
    if (!comp.id) return;
    await deleteProdutoComposicao(comp.id);
    await carregar();
  };

  return (
    <div className="mt-6 border-t border-border pt-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold">Composição / Montagem</h3>
          <p className="text-xs text-muted-foreground mt-0.5">{AVISO_COMPOSICAO_SEM_ESTOQUE}</p>
        </div>
        <button type="button" className="erp-btn-outline erp-btn-sm w-full sm:w-auto" onClick={novaComposicao}>
          <Plus className="h-4 w-4 mr-1" />
          Nova composição
        </button>
      </div>

      {erro ? <p className="text-sm text-destructive mb-2">{erro}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}

      {!loading && lista.length === 0 && !editando ? (
        <p className="text-sm text-muted-foreground">Nenhuma composição cadastrada.</p>
      ) : null}

      {lista.map((c) => (
        <div key={c.id} className="rounded-md border border-border p-3 mb-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{c.nome || labelTipoComposicao(c.tipo_composicao)}</span>
            <span className="erp-badge-outline text-xs">{labelTipoComposicao(c.tipo_composicao)}</span>
            {c.padrao ? <span className="erp-badge-success text-xs">Padrão</span> : null}
            {!c.ativo ? <span className="erp-badge-danger text-xs">Inativa</span> : null}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Comprar pronto: {c.permite_comprar_pronto ? 'sim' : 'não'} · Montar: {c.permite_montar ? 'sim' : 'não'} ·
            Componentes: {c.itens?.length ?? 0}
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            <button type="button" className="erp-btn-ghost erp-btn-sm" onClick={() => setEditando(c)}>
              Editar
            </button>
            {c.ativo ? (
              <button type="button" className="erp-btn-ghost erp-btn-sm" onClick={() => void inativar(c)}>
                Inativar
              </button>
            ) : (
              <button type="button" className="erp-btn-ghost erp-btn-sm text-destructive" onClick={() => void excluir(c)}>
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      ))}

      {editando ? (
        <div className="rounded-md border border-dashed border-border p-3 space-y-3 mt-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="erp-label">Nome da composição</label>
              <input
                className="erp-input mt-1 w-full"
                value={editando.nome || ''}
                onChange={(e) => setEditando({ ...editando, nome: e.target.value })}
              />
            </div>
            <div>
              <label className="erp-label">Tipo</label>
              <select
                className="erp-select mt-1 w-full"
                value={editando.tipo_composicao}
                onChange={(e) =>
                  setEditando({
                    ...editando,
                    tipo_composicao: e.target.value,
                    exige_servico: e.target.value === 'MONTAGEM_SOLDADA' || e.target.value === 'MONTAGEM_SERVICO_INTERNO',
                  })
                }
              >
                {TIPOS_COMPOSICAO.map((t) => (
                  <option key={t} value={t}>
                    {labelTipoComposicao(t)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={!!editando.padrao} onChange={(e) => setEditando({ ...editando, padrao: e.target.checked })} />
              Composição padrão
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!editando.permite_comprar_pronto}
                onChange={(e) => setEditando({ ...editando, permite_comprar_pronto: e.target.checked })}
              />
              Pode comprar pronto
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!editando.permite_montar}
                onChange={(e) => setEditando({ ...editando, permite_montar: e.target.checked })}
              />
              Pode montar
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!editando.exige_servico}
                onChange={(e) => setEditando({ ...editando, exige_servico: e.target.checked })}
              />
              Exige serviço
            </label>
          </div>

          <div>
            <p className="erp-label mb-2">Componentes</p>
            {(editando.itens || []).map((item, idx) => (
              <div key={idx} className="grid grid-cols-1 sm:grid-cols-12 gap-2 mb-2">
                <select
                  className="erp-select sm:col-span-7"
                  value={item.componente_produto_id || ''}
                  onChange={(e) => {
                    const itens = [...(editando.itens || [])];
                    itens[idx] = { ...itens[idx], componente_produto_id: Number(e.target.value) };
                    setEditando({ ...editando, itens });
                  }}
                >
                  <option value="">Selecione componente…</option>
                  {produtosOpcoes
                    .filter((p) => p.id !== produtoId)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.codigo_completo} — {p.descricao}
                      </option>
                    ))}
                </select>
                <input
                  type="number"
                  step="0.0001"
                  className="erp-input sm:col-span-3"
                  placeholder="Qtd/un"
                  value={item.quantidade_por_unidade_final}
                  onChange={(e) => {
                    const itens = [...(editando.itens || [])];
                    itens[idx] = { ...itens[idx], quantidade_por_unidade_final: e.target.value };
                    setEditando({ ...editando, itens });
                  }}
                />
                <button
                  type="button"
                  className="erp-btn-ghost sm:col-span-2 w-full sm:w-auto"
                  onClick={() => {
                    const itens = (editando.itens || []).filter((_, i) => i !== idx);
                    setEditando({ ...editando, itens });
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm w-full sm:w-auto"
              onClick={() => setEditando({ ...editando, itens: [...(editando.itens || []), emptyItem()] })}
            >
              + Componente
            </button>
          </div>

          <div className="flex flex-col-reverse sm:flex-row sm:justify-end items-stretch sm:items-center gap-2">
            <button type="button" className="erp-btn-outline erp-btn-sm w-full sm:w-auto" onClick={() => setEditando(null)}>
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary erp-btn-sm w-full sm:w-auto" onClick={() => void salvar()}>
              Salvar composição
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
