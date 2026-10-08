import { ChevronDown, ClipboardCheck, Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/Modal';
import { nfeSaidasService, type NFeChecklistHomologacaoResponse } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';

const STATUS_CLASS: Record<string, string> = {
  ok: 'erp-badge-success',
  alerta: 'erp-badge-warning',
  bloqueado: 'erp-badge-danger',
  nao_aplicavel: 'erp-badge-warning',
};

const STATUS_LABEL: Record<string, string> = {
  ok: 'OK',
  alerta: 'Alerta',
  bloqueado: 'Bloqueado',
  nao_aplicavel: 'N/A',
};

const SECAO_LABEL: Record<string, string> = {
  pedido_faturamento: 'Pedido / Faturamento',
  duplicatas: 'Duplicatas',
  xml: 'XML',
  danfe: 'DANFE',
  apuracao: 'Apuração',
  financeiro: 'Financeiro',
  estoque_expedicao: 'Estoque / Expedição',
  efeitos: 'Financeiro / Estoque / Expedição',
  atendimento: 'Atendimento operacional',
  reforma_tributaria: 'Reforma Tributária',
  documentos: 'UI / Documentos',
  ui: 'UI / Documentos',
  geral: 'Geral',
};

const SECAO_ORDER = [
  'pedido_faturamento',
  'xml',
  'duplicatas',
  'danfe',
  'apuracao',
  'financeiro',
  'estoque_expedicao',
  'efeitos',
  'atendimento',
  'reforma_tributaria',
  'documentos',
  'ui',
  'geral',
];

function statusGeralEhAlerta(status: string): boolean {
  return status === 'aprovado_com_alertas' || status === 'alerta';
}

type Props = {
  open: boolean;
  onClose: () => void;
  nfeSaidaId?: number | null;
  pedidoVendaId?: number | null;
  faturamentoId?: number | null;
  onResult?: (result: NFeChecklistHomologacaoResponse) => void;
};

function ChecklistSecao({
  secao,
  itens,
  defaultOpen,
}: {
  secao: string;
  itens: NFeChecklistHomologacaoResponse['itens'];
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const temBloqueio = itens.some((i) => i.status === 'bloqueado');
  const temAlerta = itens.some((i) => i.status === 'alerta');

  return (
    <section className="border border-border/60 rounded-md overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left bg-muted/30 hover:bg-muted/50 text-xs font-medium"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="uppercase tracking-wide text-muted-foreground">
          {SECAO_LABEL[secao] || secao}
        </span>
        <span className="flex items-center gap-2 shrink-0">
          {temBloqueio ? <span className="erp-badge-danger text-[10px]">Bloqueio</span> : null}
          {temAlerta ? <span className="erp-badge-warning text-[10px]">Alerta</span> : null}
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {open ? (
        <ul className="space-y-1.5 p-2">
          {itens.map((item) => (
            <li
              key={item.codigo}
              className="flex items-start gap-2 text-xs border border-border/60 rounded-md px-2 py-1.5"
            >
              <span
                className={`${STATUS_CLASS[item.status] || 'erp-badge-warning'} shrink-0 text-[10px] px-1.5 py-0`}
              >
                {STATUS_LABEL[item.status] || item.status}
              </span>
              <div>
                <p className="font-medium text-foreground">{item.label}</p>
                <p className="text-muted-foreground mt-0.5">{item.mensagem}</p>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function NFeChecklistHomologacaoModal({
  open,
  onClose,
  nfeSaidaId,
  pedidoVendaId,
  faturamentoId,
  onResult,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<NFeChecklistHomologacaoResponse | null>(null);

  const executar = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = nfeSaidaId
        ? await nfeSaidasService.checklistHomologacao(nfeSaidaId)
        : await nfeSaidasService.checklistHomologacaoGeral({
            pedido_venda_id: pedidoVendaId ?? undefined,
            faturamento_id: faturamentoId ?? undefined,
          });
      setData(res);
      onResult?.(res);
    } catch (e) {
      setData(null);
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) {
      setData(null);
      setError(null);
      return;
    }
    void executar();
  }, [open, nfeSaidaId, pedidoVendaId, faturamentoId]);

  const contagem = useMemo(() => {
    const itens = data?.itens ?? [];
    return {
      bloqueios: itens.filter((i) => i.status === 'bloqueado').length,
      alertas: itens.filter((i) => i.status === 'alerta').length,
      ok: itens.filter((i) => i.status === 'ok').length,
    };
  }, [data?.itens]);

  const secoes = useMemo(() => {
    const itens = data?.itens ?? [];
    const map = itens.reduce<Record<string, typeof itens>>((acc, item) => {
      const s = item.secao || 'geral';
      if (!acc[s]) acc[s] = [];
      acc[s].push(item);
      return acc;
    }, {});

    const prioridade = (secao: string) => {
      const lista = map[secao] ?? [];
      if (lista.some((i) => i.status === 'bloqueado')) return 0;
      if (lista.some((i) => i.status === 'alerta')) return 1;
      return 2;
    };

    return Object.keys(map).sort((a, b) => {
      const pa = prioridade(a);
      const pb = prioridade(b);
      if (pa !== pb) return pa - pb;
      const ia = SECAO_ORDER.indexOf(a);
      const ib = SECAO_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
  }, [data?.itens]);

  const statusGeral = data?.status ?? '';

  const footer = (
    <div className="flex justify-end gap-2 p-4">
      <button type="button" className="erp-btn-outline erp-btn-sm" onClick={() => void executar()}>
        Revalidar
      </button>
      <button type="button" className="erp-btn-primary erp-btn-sm" onClick={onClose}>
        Fechar
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Checklist fiscal de homologação"
      size="xl"
      footer={footer}
    >
      <p className="text-xs text-muted-foreground mb-2">
        Validação prévia sem transmissão, sem financeiro, sem estoque e sem expedição.
      </p>
      <p className="text-xs text-muted-foreground mb-4 rounded-md border border-border bg-muted/30 px-3 py-2">
        Esta validação não transmite NF-e, não gera financeiro, não movimenta estoque e não cria
        expedição.
      </p>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
          Validando pré-homologação…
        </div>
      ) : null}

      {error ? <p className="text-sm text-destructive mb-4">{error}</p> : null}

      {data && !loading ? (
        <div className="space-y-4">
          <div
            className={`rounded-md border px-3 py-2 text-sm shrink-0 ${
              statusGeral === 'bloqueado'
                ? 'border-destructive/40 bg-destructive/10 text-destructive'
                : statusGeralEhAlerta(statusGeral)
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
                  : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100'
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              <ClipboardCheck className="h-4 w-4 shrink-0" />
              {data.mensagem}
            </div>
            <p className="text-xs mt-2 opacity-90">
              {contagem.bloqueios} bloqueio(s) · {contagem.alertas} alerta(s) · {contagem.ok} itens OK
            </p>
            {statusGeral === 'aprovado' ? (
              <p className="text-xs mt-1 opacity-90">Pronto para novo teste de homologação.</p>
            ) : null}
            {statusGeralEhAlerta(statusGeral) ? (
              <p className="text-xs mt-1 opacity-90">
                Revise os alertas antes de prosseguir com um novo teste de homologação.
              </p>
            ) : null}
          </div>

          {(data.bloqueios?.length ?? 0) > 0 ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs">
              <p className="font-medium text-destructive mb-1">Bloqueios</p>
              <ul className="list-disc pl-4 space-y-0.5 text-destructive/90">
                {data.bloqueios.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {(data.alertas?.length ?? 0) > 0 ? (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs">
              <p className="font-medium text-amber-900 dark:text-amber-100 mb-1">Alertas</p>
              <ul className="list-disc pl-4 space-y-0.5 text-amber-900/90 dark:text-amber-100/90">
                {data.alertas.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="space-y-2">
            {secoes.map((secao) => (
              <ChecklistSecao
                key={secao}
                secao={secao}
                itens={(data.itens ?? []).filter((i) => (i.secao || 'geral') === secao)}
                defaultOpen={
                  ['danfe', 'xml', 'duplicatas', 'pedido_faturamento'].includes(secao) ||
                  (data.itens ?? []).some(
                    (i) => (i.secao || 'geral') === secao && i.status === 'bloqueado',
                  ) ||
                  (data.itens ?? []).some(
                    (i) => (i.secao || 'geral') === secao && i.status === 'alerta',
                  )
                }
              />
            ))}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
