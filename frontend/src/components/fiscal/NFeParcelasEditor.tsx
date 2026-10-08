import { useCallback, useEffect, useState } from 'react';
import {
  listarParcelasSugeridas,
  salvarParcelas,
  type ParcelaNFe,
} from '@/lib/nfeSaidaParcelas';

export type NFeParcelasEditorProps = {
  nfeId: number;
  valorTotal: number | string;
  dataEmissao?: string;
  onSalvo?: () => void;
};

function toNumber(v: string | number | undefined | null): number {
  if (typeof v === 'number') return v;
  if (!v) return 0;
  const n = parseFloat(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

function formatMoney(v: number): string {
  return v.toFixed(2).replace('.', ',');
}

export function NFeParcelasEditor({
  nfeId,
  valorTotal,
  dataEmissao,
  onSalvo,
}: NFeParcelasEditorProps) {
  const [parcelas, setParcelas] = useState<ParcelaNFe[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const totalNumerico = toNumber(valorTotal);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    listarParcelasSugeridas(nfeId)
      .then(({ parcelas: sugeridas }) => {
        if (!alive) return;
        setParcelas(
          sugeridas.map((p, i) => ({
            numero: p.numero || String(i + 1).padStart(3, '0'),
            vencimento: p.vencimento,
            valor: p.valor,
          })),
        );
      })
      .catch((e: any) => {
        if (alive) setErro(String(e?.response?.data?.detail || e?.message || e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [nfeId]);

  const recarregarSugeridas = useCallback(async () => {
    setErro(null);
    try {
      const { parcelas: sugeridas } = await listarParcelasSugeridas(nfeId);
      setParcelas(
        sugeridas.map((p, i) => ({
          numero: p.numero || String(i + 1).padStart(3, '0'),
          vencimento: p.vencimento,
          valor: p.valor,
        })),
      );
    } catch (e: any) {
      setErro(String(e?.response?.data?.detail || e?.message || e));
    }
  }, [nfeId]);

  const adicionarParcela = () => {
    setParcelas((prev) => [
      ...prev,
      {
        numero: String(prev.length + 1).padStart(3, '0'),
        vencimento: '',
        valor: '0,00',
      },
    ]);
  };

  const removerParcela = (idx: number) => {
    setParcelas((prev) => prev.filter((_, i) => i !== idx));
  };

  const alterarVencimento = (idx: number, venc: string) => {
    setParcelas((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, vencimento: venc } : p)),
    );
  };

  const alterarValor = (idx: number, valorTexto: string) => {
    setParcelas((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, valor: valorTexto } : p)),
    );
  };

  const somaParcelas = parcelas.reduce((acc, p) => acc + toNumber(p.valor), 0);
  const diferenca = Math.abs(somaParcelas - totalNumerico);
  const temDiferenca = diferenca > 0.01;

  const validaVencimentos = (): boolean => {
    if (!dataEmissao) return true;
    const emissao = new Date(dataEmissao);
    return parcelas.every((p) => {
      if (!p.vencimento) return true;
      return new Date(p.vencimento) >= emissao;
    });
  };

  const podeSalvar =
    !temDiferenca && !saving && parcelas.length > 0 && validaVencimentos();

  const handleSalvar = async () => {
    setErro(null);
    setSaving(true);
    try {
      await salvarParcelas(
        nfeId,
        parcelas.map((p) => ({
          numero: p.numero,
          vencimento: p.vencimento,
          valor: toNumber(p.valor).toFixed(2),
        })),
      );
      onSalvo?.();
    } catch (e: any) {
      setErro(String(e?.response?.data?.detail || e?.message || e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <p className="text-xs text-muted-foreground">Carregando parcelas…</p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Parcelas da NF-e
      </p>

      {erro ? (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">
          {erro}
        </p>
      ) : null}

      <div className="space-y-2">
        {parcelas.map((p, idx) => {
          const vencInvalido =
            !!dataEmissao &&
            !!p.vencimento &&
            new Date(p.vencimento) < new Date(dataEmissao);
          const valorInvalido = toNumber(p.valor) <= 0;
          return (
            <div
              key={idx}
              className="grid grid-cols-[60px_1fr_1fr_90px] gap-2 items-end border border-border rounded p-2"
            >
              <div>
                <label className="block text-[10px] text-muted-foreground">
                  Nº
                </label>
                <input
                  type="text"
                  value={p.numero}
                  readOnly
                  className="block w-full rounded border border-border text-sm px-1 py-0.5 bg-muted/30"
                />
              </div>
              <div>
                <label className="block text-[10px] text-muted-foreground">
                  Vencimento
                </label>
                <input
                  type="date"
                  value={p.vencimento}
                  min={dataEmissao}
                  onChange={(e) => alterarVencimento(idx, e.target.value)}
                  className={`block w-full rounded border text-sm px-1 py-0.5 ${
                    vencInvalido ? 'border-red-500' : 'border-border'
                  }`}
                />
                {vencInvalido ? (
                  <p className="text-[10px] text-red-600 mt-0.5">
                    Antes da emissão
                  </p>
                ) : null}
              </div>
              <div>
                <label className="block text-[10px] text-muted-foreground">
                  Valor (R$)
                </label>
                <input
                  type="text"
                  value={p.valor}
                  onChange={(e) => alterarValor(idx, e.target.value)}
                  placeholder="0,00"
                  className={`block w-full rounded border text-sm px-1 py-0.5 ${
                    valorInvalido ? 'border-red-500' : 'border-border'
                  }`}
                />
                {valorInvalido ? (
                  <p className="text-[10px] text-red-600 mt-0.5">
                    Valor inválido
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => removerParcela(idx)}
                className="erp-btn-outline erp-btn-sm text-xs"
                disabled={parcelas.length <= 1}
                title="Remover parcela"
              >
                Remover
              </button>
            </div>
          );
        })}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={adicionarParcela}
          className="erp-btn-outline erp-btn-sm text-xs"
        >
          + Adicionar parcela
        </button>
        <button
          type="button"
          onClick={recarregarSugeridas}
          className="erp-btn-outline erp-btn-sm text-xs"
        >
          Sugerir do pedido
        </button>
      </div>

      <div className="rounded-md border border-border p-2 space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Total NF:</span>
          <span className="font-medium">R$ {formatMoney(totalNumerico)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Soma parcelas:</span>
          <span className="font-medium">R$ {formatMoney(somaParcelas)}</span>
        </div>
        {temDiferenca ? (
          <div className="flex justify-between text-red-600">
            <span>Diferença:</span>
            <span className="font-medium">R$ {formatMoney(diferenca)}</span>
          </div>
        ) : null}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSalvar}
          disabled={!podeSalvar}
          className={`erp-btn erp-btn-sm ${
            podeSalvar ? 'erp-btn-primary' : 'opacity-50 cursor-not-allowed'
          }`}
        >
          {saving ? 'Salvando…' : 'Salvar parcelas'}
        </button>
      </div>
    </div>
  );
}
