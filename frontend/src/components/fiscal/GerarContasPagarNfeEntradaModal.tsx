import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { formatDateBr } from '@/lib/dateBr';
import { formatCnpjDisplay } from '@/lib/cnpj';
import { formatMoneyBRL } from '@/lib/money';
import { apiErrorMessage } from '@/services/api/config';
import {
  financeiroService,
  type FormaPagamentoFixa,
  type TituloFinanceiro,
} from '@/services/api/financeiro';
import {
  nfeHistoricaEntradaImportadaService,
  type NFeGerarContasPagarParcela,
  type NFeGerarContasPagarPreview,
} from '@/services/api/nfeHistoricaEntradaImportada';
import { formatarAvisoPendenciasOperacionaisNfeEntrada } from '@/lib/conferenciaNfeLabels';

const TOLERANCIA_PARCELAS = 0.05;

type Props = {
  open: boolean;
  nfeEntradaId: number | null;
  onClose: () => void;
  onGenerated: (payload: { titulo: TituloFinanceiro; financeiro_gerado: boolean }) => void;
};

type Step = 1 | 2 | 3 | 4;

function somaParcelas(parcelas: NFeGerarContasPagarParcela[]): number {
  return parcelas.reduce((acc, p) => acc + (Number.parseFloat(String(p.valor).replace(',', '.')) || 0), 0);
}

export function GerarContasPagarNfeEntradaModal({ open, nfeEntradaId, onClose, onGenerated }: Props) {
  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [preview, setPreview] = useState<NFeGerarContasPagarPreview | null>(null);
  const [parcelas, setParcelas] = useState<NFeGerarContasPagarParcela[]>([]);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [centros, setCentros] = useState<{ id: number; nome: string }[]>([]);
  const [contasOpts, setContasOpts] = useState<{ id: number; nome: string }[]>([]);
  const [formasOpts, setFormasOpts] = useState<FormaPagamentoFixa[]>([]);
  const [classificacao, setClassificacao] = useState({
    categoria_id: '',
    centro_custo_id: '',
    forma_pagamento_prevista_codigo: '',
    conta_financeira_prevista: '',
    observacoes: '',
  });
  const [confirmarPendencias, setConfirmarPendencias] = useState(false);

  useEffect(() => {
    if (!open || !nfeEntradaId) {
      setStep(1);
      setPreview(null);
      setParcelas([]);
      setErro(null);
      setConfirmarPendencias(false);
      return;
    }
    setLoading(true);
    setErro(null);
    setStep(1);
    void Promise.all([
      nfeHistoricaEntradaImportadaService.previewContasPagar(nfeEntradaId),
      financeiroService.listCategorias({ limit: 200, tipo: 'DESPESA' }),
      financeiroService.listCentrosCusto({ limit: 200 }),
      financeiroService.listContasAtivas(),
      financeiroService.listFormasAtivas(),
    ])
      .then(([prev, cat, cc, contas, formas]) => {
        setPreview(prev);
        setParcelas(prev.parcelas.map((p) => ({ ...p })));
        setClassificacao({
          categoria_id: prev.categoria_sugerida_id ? String(prev.categoria_sugerida_id) : '',
          centro_custo_id: '',
          forma_pagamento_prevista_codigo: '',
          conta_financeira_prevista: '',
          observacoes: '',
        });
        setCategorias((cat.results ?? []).filter((c) => c.ativo));
        setCentros((cc.results ?? []).filter((c) => c.ativo));
        setContasOpts(contas.map((c) => ({ id: c.id, nome: c.nome })));
        setFormasOpts(formas);
      })
      .catch((e) => {
        setErro(apiErrorMessage(e, { fallback: 'Não foi possível carregar o preview financeiro.' }));
        setPreview(null);
      })
      .finally(() => setLoading(false));
  }, [open, nfeEntradaId]);

  const total = useMemo(() => Number.parseFloat(String(preview?.origem.valor_total ?? 0)), [preview]);
  const soma = useMemo(() => somaParcelas(parcelas), [parcelas]);
  const diffParcelas = Math.abs(soma - total);
  const parcelasValidas = parcelas.length > 0 && parcelas.every((p) => p.vencimento && Number(p.valor) > 0);
  const somaValida = diffParcelas <= TOLERANCIA_PARCELAS;
  const exigeConfirmacaoPendencias = Boolean(preview?.possui_pendencias_operacionais);
  const confirmacaoPendenciasOk = !exigeConfirmacaoPendencias || confirmarPendencias;

  const categoriaNome = categorias.find((c) => String(c.id) === classificacao.categoria_id)?.nome ?? '—';
  const centroNome = centros.find((c) => String(c.id) === classificacao.centro_custo_id)?.nome ?? '—';
  const formaNome =
    formasOpts.find((f) => f.codigo === classificacao.forma_pagamento_prevista_codigo)?.label ?? '—';
  const contaNome =
    contasOpts.find((c) => String(c.id) === classificacao.conta_financeira_prevista)?.nome ?? '—';

  const confirmar = async () => {
    if (!nfeEntradaId || !preview || !parcelasValidas || !somaValida || !confirmacaoPendenciasOk) return;
    setSaving(true);
    setErro(null);
    try {
      const res = await nfeHistoricaEntradaImportadaService.gerarContasPagar(nfeEntradaId, {
        parcelas,
        categoria: classificacao.categoria_id ? Number(classificacao.categoria_id) : null,
        centro_custo: classificacao.centro_custo_id ? Number(classificacao.centro_custo_id) : null,
        forma_pagamento_prevista_codigo: classificacao.forma_pagamento_prevista_codigo || undefined,
        conta_financeira_prevista: classificacao.conta_financeira_prevista
          ? Number(classificacao.conta_financeira_prevista)
          : null,
        observacoes: classificacao.observacoes,
        confirmar_pendencias_operacionais: exigeConfirmacaoPendencias ? confirmarPendencias : undefined,
      });
      onGenerated({ titulo: res.titulo, financeiro_gerado: res.financeiro_gerado });
      onClose();
    } catch (e) {
      setErro(apiErrorMessage(e, { fallback: 'Não foi possível gerar as contas a pagar.' }));
    } finally {
      setSaving(false);
    }
  };

  const footer = (
    <div className="p-4 flex flex-wrap items-center justify-between gap-2">
      <div className="text-xs text-muted-foreground">Etapa {step} de 4</div>
      <div className="flex flex-wrap gap-2">
        {step > 1 ? (
          <button type="button" className="erp-btn-outline erp-btn-sm" disabled={saving} onClick={() => setStep((s) => (s - 1) as Step)}>
            <ChevronLeft className="h-3 w-3 mr-1" />
            Voltar
          </button>
        ) : null}
        {step < 4 ? (
          <button
            type="button"
            className="erp-btn-primary erp-btn-sm"
            disabled={loading || !preview || (step === 2 && (!parcelasValidas || !somaValida))}
            onClick={() => setStep((s) => (s + 1) as Step)}
          >
            Avançar
            <ChevronRight className="h-3 w-3 ml-1" />
          </button>
        ) : (
          <button
            type="button"
            className="erp-btn-primary erp-btn-sm"
            disabled={saving || !parcelasValidas || !somaValida || !confirmacaoPendenciasOk}
            onClick={() => void confirmar()}
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
            Gerar contas a pagar
          </button>
        )}
      </div>
    </div>
  );

  return (
    <Modal isOpen={open} onClose={onClose} title="Gerar contas a pagar" size="lg" footer={footer}>
      <p className="text-sm text-muted-foreground mb-4">Revise as parcelas antes de gerar o financeiro.</p>

      {preview?.aviso_origem_parcelas ? (
        <p className="text-sm text-sky-900 bg-sky-50 border border-sky-200 rounded-md px-3 py-2 mb-4">
          {preview.aviso_origem_parcelas}
        </p>
      ) : null}

      {preview?.origem_parcelas === 'XML' ? (
        <p className="text-sm text-emerald-900 bg-emerald-50 border border-emerald-200 rounded-md px-3 py-2 mb-4">
          Parcelas sugeridas a partir das duplicatas do XML (vencimentos e valores preservados).
        </p>
      ) : null}

      {preview?.possui_pendencias_operacionais ? (
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-4">
          {formatarAvisoPendenciasOperacionaisNfeEntrada(
            preview.aviso_pendencias_wizard || preview.aviso_pendencias_operacionais,
          )}
        </p>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
          Carregando preview…
        </div>
      ) : null}

      {erro ? <p className="text-sm text-destructive mb-3">{erro}</p> : null}

      {preview && !loading ? (
        <>
          {step === 1 ? (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Fornecedor</p>
                  <p>{preview.fornecedor.nome}</p>
                  {preview.fornecedor.cnpj ? (
                    <p className="text-xs text-muted-foreground">{formatCnpjDisplay(preview.fornecedor.cnpj)}</p>
                  ) : null}
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">NF-e Entrada</p>
                  <p>
                    nº {preview.origem.numero}
                    {preview.origem.serie ? ` · Série ${preview.origem.serie}` : ''}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Emissão</p>
                  <p>{preview.origem.data_emissao ? formatDateBr(preview.origem.data_emissao) : '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Importação</p>
                  <p>
                    {preview.origem.data_importacao
                      ? formatDateBr(preview.origem.data_importacao.slice(0, 10))
                      : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Valor total</p>
                  <p className="font-medium">{formatMoneyBRL(total)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase">Parcelas sugeridas</p>
                  <p>{preview.quantidade_parcelas_sugeridas}</p>
                </div>
                {preview.origem.pedido_compra_numero ? (
                  <div className="sm:col-span-2">
                    <p className="text-xs text-muted-foreground uppercase">Pedido de compra</p>
                    <p>{preview.origem.pedido_compra_numero}</p>
                  </div>
                ) : null}
              </div>
              {preview.origem.chave_acesso ? (
                <p className="text-xs text-muted-foreground font-mono break-all">Chave: {preview.origem.chave_acesso}</p>
              ) : null}
            </div>
          ) : null}

          {step === 2 ? (
            <div className="space-y-3">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b">
                      <th className="py-2 pr-2">Parcela</th>
                      <th className="py-2 pr-2">Vencimento</th>
                      <th className="py-2 pr-2">Valor</th>
                      <th className="py-2">Observações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parcelas.map((p, idx) => (
                      <tr key={`${p.numero_parcela}-${idx}`} className="border-b border-border/60">
                        <td className="py-2 pr-2">{p.numero_parcela}</td>
                        <td className="py-2 pr-2">
                          <input
                            type="date"
                            className="erp-input erp-input-sm w-full"
                            value={p.vencimento?.slice(0, 10) ?? ''}
                            onChange={(e) => {
                              const next = [...parcelas];
                              next[idx] = { ...next[idx], vencimento: e.target.value };
                              setParcelas(next);
                            }}
                          />
                        </td>
                        <td className="py-2 pr-2">
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            className="erp-input erp-input-sm w-full"
                            value={p.valor}
                            onChange={(e) => {
                              const next = [...parcelas];
                              next[idx] = { ...next[idx], valor: e.target.value };
                              setParcelas(next);
                            }}
                          />
                        </td>
                        <td className="py-2">
                          <input
                            type="text"
                            className="erp-input erp-input-sm w-full"
                            value={p.observacoes ?? ''}
                            onChange={(e) => {
                              const next = [...parcelas];
                              next[idx] = { ...next[idx], observacoes: e.target.value };
                              setParcelas(next);
                            }}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap gap-4 text-sm">
                <span>Total NF-e: {formatMoneyBRL(total)}</span>
                <span>Soma parcelas: {formatMoneyBRL(soma)}</span>
              </div>
              {!somaValida ? (
                <p className="text-sm text-destructive">A soma das parcelas não confere com o valor total.</p>
              ) : null}
            </div>
          ) : null}

          {step === 3 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Categoria</span>
                <select
                  className="erp-input w-full"
                  value={classificacao.categoria_id}
                  onChange={(e) => setClassificacao((f) => ({ ...f, categoria_id: e.target.value }))}
                >
                  <option value="">Selecione…</option>
                  {categorias.map((c) => (
                    <option key={c.id} value={c.id}>{c.nome}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Centro de custo</span>
                <select
                  className="erp-input w-full"
                  value={classificacao.centro_custo_id}
                  onChange={(e) => setClassificacao((f) => ({ ...f, centro_custo_id: e.target.value }))}
                >
                  <option value="">Opcional</option>
                  {centros.map((c) => (
                    <option key={c.id} value={c.id}>{c.nome}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Forma de pagamento prevista</span>
                <select
                  className="erp-input w-full"
                  value={classificacao.forma_pagamento_prevista_codigo}
                  onChange={(e) =>
                    setClassificacao((f) => ({ ...f, forma_pagamento_prevista_codigo: e.target.value }))
                  }
                >
                  <option value="">Opcional</option>
                  {formasOpts.map((f) => (
                    <option key={f.codigo} value={f.codigo}>{f.label}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Conta / caixa prevista</span>
                <select
                  className="erp-input w-full"
                  value={classificacao.conta_financeira_prevista}
                  onChange={(e) =>
                    setClassificacao((f) => ({ ...f, conta_financeira_prevista: e.target.value }))
                  }
                >
                  <option value="">Opcional</option>
                  {contasOpts.map((c) => (
                    <option key={c.id} value={c.id}>{c.nome}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className="text-xs text-muted-foreground">Observações</span>
                <textarea
                  className="erp-input w-full min-h-[72px]"
                  value={classificacao.observacoes}
                  onChange={(e) => setClassificacao((f) => ({ ...f, observacoes: e.target.value }))}
                />
              </label>
            </div>
          ) : null}

          {step === 4 ? (
            <div className="space-y-2 text-sm">
              {exigeConfirmacaoPendencias ? (
                <label className="flex items-start gap-2 text-xs border border-amber-200 bg-amber-50 rounded-md p-3 mb-2">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={confirmarPendencias}
                    onChange={(e) => setConfirmarPendencias(e.target.checked)}
                  />
                  <span>
                    Estou ciente de que o financeiro será gerado e a conferência operacional continuará pendente.
                  </span>
                </label>
              ) : null}
              <p><span className="text-muted-foreground">Fornecedor:</span> {preview.fornecedor.nome}</p>
              <p><span className="text-muted-foreground">Origem:</span> NF-e Entrada nº {preview.origem.numero}</p>
              {preview.origem.pedido_compra_numero ? (
                <p><span className="text-muted-foreground">Pedido:</span> {preview.origem.pedido_compra_numero}</p>
              ) : null}
              <p><span className="text-muted-foreground">Total:</span> {formatMoneyBRL(total)}</p>
              <p><span className="text-muted-foreground">Categoria:</span> {categoriaNome}</p>
              <p><span className="text-muted-foreground">Centro de custo:</span> {centroNome}</p>
              <p><span className="text-muted-foreground">Forma prevista:</span> {formaNome}</p>
              <p><span className="text-muted-foreground">Conta prevista:</span> {contaNome}</p>
              <div>
                <p className="text-muted-foreground mb-1">Parcelas:</p>
                <ul className="list-disc pl-5 space-y-0.5">
                  {parcelas.map((p) => (
                    <li key={`res-${p.numero_parcela}`}>
                      #{p.numero_parcela} — {formatDateBr(p.vencimento)} — {formatMoneyBRL(Number(p.valor))}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </Modal>
  );
}
