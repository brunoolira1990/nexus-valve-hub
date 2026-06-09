import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Circle } from 'lucide-react';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';

type ChecklistItem = {
  item: string;
  ok: boolean;
  nota?: string;
};

type ChecklistResponse = {
  checklist_fiscal?: ChecklistItem[];
  checklist_saida?: ChecklistItem[];
  checklist_entrada?: ChecklistItem[];
  metricas?: Record<string, number | string | boolean>;
  criticos?: { mensagem: string }[];
  avisos?: { mensagem: string }[];
  avisos_entrada?: { mensagem: string }[];
};

function ChecklistBloco({
  titulo,
  subtitulo,
  itens,
}: {
  titulo: string;
  subtitulo?: string;
  itens: ChecklistItem[];
}) {
  if (!itens.length) return null;
  return (
    <div className="space-y-2">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titulo}</h3>
        {subtitulo ? <p className="text-xs text-muted-foreground mt-0.5">{subtitulo}</p> : null}
      </div>
      <ul className="space-y-2">
        {itens.map((item) => (
          <li key={item.item} className="flex items-start gap-2 text-sm">
            {item.ok ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <Circle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            )}
            <span>
              <span className={item.ok ? 'text-foreground' : 'text-foreground/90'}>{item.item}</span>
              {item.nota ? <span className="block text-xs text-muted-foreground">{item.nota}</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ChecklistFiscalMinimo() {
  const [data, setData] = useState<ChecklistResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void regrasFiscaisService
      .checklistProducao()
      .then((res) => {
        if (active) setData(res);
      })
      .catch(() => {
        if (active) setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const saida = data?.checklist_saida ?? data?.checklist_fiscal?.slice(0, 6) ?? [];
  const entrada = data?.checklist_entrada ?? data?.checklist_fiscal?.slice(6) ?? [];
  const avisosEntrada = data?.avisos_entrada ?? [];

  return (
    <section className="rounded-lg border border-border bg-card p-4 mb-4 space-y-4">
      <div>
        <h2 className="text-sm font-semibold">Checklist fiscal mínimo para produção</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Orientação informativa. Cadastre as regras fiscais reais com apoio do contador — o sistema não cria regras
          automaticamente.
        </p>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Carregando checklist…</p> : null}

      {!loading ? (
        <>
          <ChecklistBloco
            titulo="Pronto para venda/saída"
            subtitulo="Obrigatório para iniciar produção geral."
            itens={saida}
          />
          <ChecklistBloco
            titulo="Pendente para entrada fiscal"
            subtitulo="Obrigatório ao finalizar NF-e Entrada fiscal — não bloqueia produção geral."
            itens={entrada}
          />
        </>
      ) : null}

      {!loading && avisosEntrada.length > 0 ? (
        <div className="rounded-md border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20 px-3 py-2 text-xs text-amber-900 dark:text-amber-100 space-y-1">
          <div className="flex items-center gap-1.5 font-medium">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            Entrada fiscal
          </div>
          {avisosEntrada.slice(0, 4).map((a) => (
            <p key={a.mensagem}>{a.mensagem}</p>
          ))}
        </div>
      ) : null}

      {!loading && data?.criticos?.length ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive space-y-1">
          {data.criticos.slice(0, 3).map((c) => (
            <p key={c.mensagem}>{c.mensagem}</p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
