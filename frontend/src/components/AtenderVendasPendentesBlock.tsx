import { useCallback, useEffect, useState } from 'react';
import {
  atendimentosEstoqueService,
  type SugestaoAtendimentoConferencia,
  type SugestoesAtendimentoResponse,
} from '@/services/api/outros';
import { apiErrorMessage } from '@/services/api/config';

type Props = {
  itemConferenciaId: number;
  onVinculado?: () => void;
};

export function AtenderVendasPendentesBlock({ itemConferenciaId, onVinculado }: Props) {
  const [data, setData] = useState<SugestoesAtendimentoResponse | null>(null);
  const [erro, setErro] = useState('');
  const [busy, setBusy] = useState(false);
  const [qtyByAtend, setQtyByAtend] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    try {
      const res = await atendimentosEstoqueService.sugestoes(itemConferenciaId);
      setData(res);
      const initial: Record<number, string> = {};
      res.sugestoes.forEach((s) => {
        initial[s.atendimento_id] = s.quantidade_sugerida;
      });
      setQtyByAtend(initial);
      setErro('');
    } catch (e) {
      setErro(apiErrorMessage(e));
    }
  }, [itemConferenciaId]);

  useEffect(() => {
    void load();
  }, [load]);

  const vincular = async (sug: SugestaoAtendimentoConferencia) => {
    const q = qtyByAtend[sug.atendimento_id] || sug.quantidade_sugerida;
    setBusy(true);
    setErro('');
    try {
      await atendimentosEstoqueService.vincular({
        item_conferencia_id: itemConferenciaId,
        atendimento_id: sug.atendimento_id,
        quantidade: q,
      });
      await load();
      onVinculado?.();
    } catch (e) {
      setErro(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (!data && !erro) return <p className="text-[9px] text-muted-foreground mt-1">Carregando atendimentos…</p>;

  return (
    <div className="mt-2 pt-2 border-t border-border/60 space-y-1">
      <p className="text-[9px] font-medium text-foreground">Atender vendas pendentes</p>
      <p className="text-[9px] text-amber-700 dark:text-amber-400">
        Este vínculo atende o compromisso da venda antecipada, mas ainda não movimenta estoque físico.
      </p>
      {data && (
        <p className="text-[9px] text-muted-foreground">
          Disponível na linha: {data.quantidade_disponivel} / NF: {data.quantidade_nf}
        </p>
      )}
      {(data?.vinculos ?? []).map((v) => (
        <span key={v.linha_id} className="erp-badge-info text-[9px] mr-1">
          Atende NF saída {v.numero_nf_saida} ({v.quantidade})
        </span>
      ))}
      {(data?.sugestoes ?? []).map((s) => (
        <div key={s.atendimento_id} className="flex flex-wrap items-center gap-1 text-[9px]">
          <span className="text-muted-foreground">
            NF {s.numero_nf_saida} · {s.cliente_nome} · pend. {s.quantidade_pendente} · {s.dias_em_aberto}d
          </span>
          <input
            className="erp-input h-6 w-16 text-[9px]"
            value={qtyByAtend[s.atendimento_id] ?? s.quantidade_sugerida}
            onChange={(e) => setQtyByAtend((p) => ({ ...p, [s.atendimento_id]: e.target.value }))}
          />
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm text-[9px] py-0"
            disabled={busy}
            onClick={() => void vincular(s)}
          >
            Vincular
          </button>
        </div>
      ))}
      {data && data.sugestoes.length === 0 && !(data.vinculos?.length) && (
        <p className="text-[9px] text-muted-foreground">Nenhum atendimento pendente para este produto.</p>
      )}
      {erro && <p className="text-[9px] text-destructive">{erro}</p>}
    </div>
  );
}
