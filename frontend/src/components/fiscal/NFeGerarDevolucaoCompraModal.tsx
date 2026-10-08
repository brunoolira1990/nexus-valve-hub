import { useEffect, useState } from 'react';
import type {
  ItemConferenciaNFeEntrada,
  ResultadoGerarSaidaDevolucaoCompra,
} from '@/types';
import { nfeEntradaConferenciaService } from '@/services/api/nfeEntradaConferencia';

type Motivo = 'NAO_CONFORME' | 'DEFEITO' | 'ERRO_PEDIDO' | 'AVARIA_TRANSPORTE' | 'OUTRO';

const MOTIVOS: Array<{ value: Motivo; label: string }> = [
  { value: 'NAO_CONFORME', label: 'Mercadoria não conforme' },
  { value: 'DEFEITO', label: 'Mercadoria com defeito' },
  { value: 'ERRO_PEDIDO', label: 'Erro de pedido' },
  { value: 'AVARIA_TRANSPORTE', label: 'Avaria no transporte' },
  { value: 'OUTRO', label: 'Outro (descrever abaixo)' },
];

interface Props {
  open: boolean;
  nfeHistoricaId: number;
  itensConferencia: ItemConferenciaNFeEntrada[];
  onClose: () => void;
  onSuccess: (resultado: ResultadoGerarSaidaDevolucaoCompra) => void;
}

interface ItemSelecionado {
  marcado: boolean;
  quantidade: string;
}

export function NFeGerarDevolucaoCompraModal({
  open,
  nfeHistoricaId,
  itensConferencia,
  onClose,
  onSuccess,
}: Props) {
  const [selecionados, setSelecionados] = useState<Record<number, ItemSelecionado>>({});
  const [motivo, setMotivo] = useState<Motivo>('NAO_CONFORME');
  const [observacao, setObservacao] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const init: Record<number, ItemSelecionado> = {};
    for (const it of itensConferencia) {
      const saldo = Number(it.quantidade_estoque_calculada ?? it.quantidade_nf ?? 0);
      init[it.id] = { marcado: saldo > 0, quantidade: saldo > 0 ? String(saldo) : '' };
    }
    setSelecionados(init);
    setMotivo('NAO_CONFORME');
    setObservacao('');
    setErro(null);
  }, [open, itensConferencia]);

  if (!open) return null;

  const totaisMarcados = Object.values(selecionados).filter((s) => s.marcado).length;
  const precisaObservacao = motivo === 'OUTRO' && !observacao.trim();

  const gerar = async () => {
    setErro(null);
    if (totaisMarcados === 0) {
      setErro('Selecione ao menos um item.');
      return;
    }
    if (precisaObservacao) {
      setErro('Motivo "Outro" exige observação.');
      return;
    }

    const itens = Object.entries(selecionados)
      .filter(([, s]) => s.marcado)
      .map(([idStr, s]) => {
        const qtd = Number(String(s.quantidade).replace(',', '.'));
        return { item_conferencia_id: Number(idStr), quantidade: String(qtd) };
      })
      .filter((it) => Number(it.quantidade) > 0);

    if (itens.length === 0) {
      setErro('Informe quantidade maior que zero em pelo menos um item.');
      return;
    }

    setEnviando(true);
    try {
      const res = await nfeEntradaConferenciaService.gerarSaidaDevolucaoCompra(
        nfeHistoricaId,
        { itens, motivo, observacao: observacao.trim() || undefined },
      );
      onSuccess(res);
    } catch (e: any) {
      const msg =
        e?.response?.data?.mensagem ||
        e?.response?.data?.detail ||
        (e?.response?.status === 400
          ? 'Dados inválidos. Revise as quantidades e o motivo.'
          : 'Erro técnico. Tente novamente.');
      setErro(msg);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="nexus-card w-full max-w-3xl max-h-[90vh] overflow-y-auto p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-semibold">Gerar devolução ao fornecedor</h2>
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={onClose}
            disabled={enviando}
          >
            Fechar
          </button>
        </div>

        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
          Será criado um <strong>rascunho</strong> de NF-e de Saída. Nada é transmitido à SEFAZ.
        </p>

        <div className="space-y-2">
          <p className="text-xs font-medium">Itens a devolver</p>
          <div className="border border-border rounded divide-y divide-border max-h-64 overflow-y-auto">
            {itensConferencia.map((it) => {
              const sel = selecionados[it.id];
              if (!sel) return null;
              return (
                <div key={it.id} className="flex items-center gap-3 px-3 py-2 text-xs">
                  <input
                    type="checkbox"
                    checked={sel.marcado}
                    onChange={(e) =>
                      setSelecionados((prev) => ({
                        ...prev,
                        [it.id]: { ...sel, marcado: e.target.checked },
                      }))
                    }
                  />
                  <span className="flex-1 truncate">
                    {it.produto_nome || it.descricao_xml || `Item ${it.id}`}
                  </span>
                  <input
                    type="number"
                    step="0.001"
                    min="0"
                    className="erp-input w-24 text-right"
                    value={sel.quantidade}
                    onChange={(e) =>
                      setSelecionados((prev) => ({
                        ...prev,
                        [it.id]: { ...sel, quantidade: e.target.value },
                      }))
                    }
                    disabled={!sel.marcado}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-xs space-y-1">
            <span className="font-medium">Motivo</span>
            <select
              className="erp-input w-full"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value as Motivo)}
            >
              {MOTIVOS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="text-xs space-y-1 block">
          <span className="font-medium">
            Observação {motivo === 'OUTRO' ? '(obrigatória)' : '(opcional)'}
          </span>
          <textarea
            className="erp-input w-full"
            rows={3}
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            placeholder="Detalhes complementares..."
          />
        </label>

        {erro ? (
          <p className="text-xs text-destructive bg-destructive/10 border border-destructive/30 rounded p-2">
            {erro}
          </p>
        ) : null}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={onClose}
            disabled={enviando}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="erp-btn-primary erp-btn-sm"
            onClick={() => void gerar()}
            disabled={enviando || totaisMarcados === 0 || precisaObservacao}
          >
            {enviando ? 'Gerando...' : 'Gerar rascunho'}
          </button>
        </div>
      </div>
    </div>
  );
}
