import { useEffect, useState } from 'react';
import { ArrowRight, History, Loader2, Zap } from 'lucide-react';
import { Badge } from '@/components/nexus';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  AUDITORIA_ESCOPO_TEXTO,
  AUDITORIA_VALOR_PROTEGIDO,
  campoEhProtegido,
  entradasAlteracao,
  formatarValorAuditoria,
  labelAcaoAuditoria,
  labelCampoAuditoria,
  labelOperacaoAuditoria,
} from '@/lib/auditoriaHistorico';
import {
  auditoriaService,
  type RegistroAuditoria,
} from '@/services/api/auditoria';
import { apiErrorMessage, getApiErrorStatus, isApiForbidden } from '@/services/api/config';

// O par appLabel/modelName tem de bater com MODELOS_AUDITADOS do backend;
// fora dele a view responde 404 e a aba mostra "Recurso não encontrado".
export type HistoricoEscopo =
  | { appLabel: 'cadastros'; modelName: 'cliente' }
  | { appLabel: 'cadastros'; modelName: 'fornecedor' }
  // Transportadora: o modelName é o nome da classe em minúsculas, igual a 'familiaproduto'.
  | { appLabel: 'cadastros'; modelName: 'transportadora' }
  | { appLabel: 'produtos'; modelName: 'produto' }
  // Família: no escopo de auditoria o modelName é o nome da classe em minúsculas, não "familia".
  | { appLabel: 'produtos'; modelName: 'familiaproduto' }
  // Documentos (Sprint 3.18): mesma regra — modelName é a classe em minúsculas.
  | { appLabel: 'comercial'; modelName: 'cotacaofornecedor' }
  | { appLabel: 'comercial'; modelName: 'proposta' }
  | { appLabel: 'comercial'; modelName: 'pedidovenda' }
  | { appLabel: 'comercial'; modelName: 'pedidocompra' }
  | { appLabel: 'fiscal'; modelName: 'nfesaida' }
  | { appLabel: 'fiscal'; modelName: 'nfeentrada' }
  // Fase 1 da entrada de terceiros: os mesmos pares de MODELOS_AUDITADOS
  // (backend/apps/auditoria/escopo.py). Grafia real do model_name Django:
  // 'nfeentradahistoricaimportada' com "c" (Historica + Importada).
  | { appLabel: 'fiscal'; modelName: 'nfeentradahistoricaimportada' }
  | { appLabel: 'fiscal'; modelName: 'nfeentradaconferencia' }
  | { appLabel: 'fiscal'; modelName: 'ctehistoricoimportado' };

type Props = {
  objectId?: number | null;
  active?: boolean;
  enabled?: boolean;
} & HistoricoEscopo;

function formatarDataLocal(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR');
  } catch {
    return iso;
  }
}

function temValor(valor: unknown): boolean {
  return valor !== null && valor !== undefined && valor !== '';
}

/**
 * Item de timeline do historico (renderer do PR 2, extraido no PR 4 sem
 * alteracao de markup). O HistoricoAlteracoesPanel renderiza item a item
 * exatamente como antes; o UnifiedEntradaFeed (rail da conferencia NF-e)
 * reutiliza este MESMO renderer — mesmo EVENTO (badge Zap + ACAO_LABELS),
 * mesmo diff de campos, mesmos testids — sem duplicar o parser do PR 2.
 */
export function ItemHistoricoAuditoria({ reg }: { reg: RegistroAuditoria }) {
  // Contrato do PR 1 (coluna `acao`): acao != '' renderiza como
  // EVENTO — ícone + label humano de ACAO_LABELS — e NÃO como
  // diff de campos. acao == ''/'ausente' mantém o render antigo
  // (retrocompatibilidade obrigatória; fixtures pré-PR1 não têm
  // a chave nenhuma).
  const ehEvento = Boolean(reg.acao);
  return (
  <li
    key={reg.id}
    className="relative"
    data-testid={`auditoria-evento-${reg.id}`}
    data-operacao={reg.operacao}
    data-acao={reg.acao || undefined}
  >
    <span
      aria-hidden
      className="absolute -left-[26px] top-4 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary/70"
    />
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {ehEvento ? (
            // Badge (nexus) rendera <span> próprio sem espalhar props — o testid
            // vai no wrapper, não no Badge.
            <span data-testid={`auditoria-acao-${reg.id}`} className="inline-flex">
              <Badge variant="info">
                <Zap aria-hidden className="mr-1 h-3 w-3" />
                {labelAcaoAuditoria(reg.acao as string)}
              </Badge>
            </span>
          ) : (
            <Badge variant={reg.operacao === 'CREATE' ? 'info' : 'neutral'}>
              {labelOperacaoAuditoria(reg.operacao)}
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            {reg.ator?.nome || 'Sistema / usuário removido'}
          </span>
        </div>
        <span className="text-xs text-muted-foreground tabular-nums">
          {formatarDataLocal(reg.criado_em)}
        </span>
      </div>

      {ehEvento ? null : (
      <ul className="mt-3 space-y-2.5">
        {entradasAlteracao(reg).map(({ campo, alt }) => {
          const antes = 'antes' in alt ? alt.antes : null;
          const depois = 'depois' in alt ? alt.depois : null;
          return (
            <li
              key={campo}
              className="flex flex-wrap items-center gap-x-3 gap-y-1.5"
              data-testid={`auditoria-campo-${campo}`}
            >
              <span className="min-w-40 text-xs font-medium text-muted-foreground">
                {labelCampoAuditoria(campo)}
              </span>
              {campoEhProtegido(alt) ? (
                <Badge variant="neutral">{AUDITORIA_VALOR_PROTEGIDO}</Badge>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  {temValor(antes) ? (
                    <span data-testid={`auditoria-antes-${campo}`} className="inline-flex">
                      <Badge variant="danger" className="line-through">
                        {formatarValorAuditoria(antes)}
                      </Badge>
                    </span>
                  ) : null}
                  {temValor(antes) && temValor(depois) ? (
                    <ArrowRight aria-hidden className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : null}
                  {temValor(depois) ? (
                    <span data-testid={`auditoria-depois-${campo}`} className="inline-flex">
                      <Badge variant="success">{formatarValorAuditoria(depois)}</Badge>
                    </span>
                  ) : null}
                  {!temValor(antes) && !temValor(depois) ? (
                    <Badge variant="neutral">{formatarValorAuditoria(null)}</Badge>
                  ) : null}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      )}
    </div>
  </li>
  );
}

export function HistoricoAlteracoesPanel({
  appLabel,
  modelName,
  objectId,
  active = true,
  enabled = true,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [registros, setRegistros] = useState<RegistroAuditoria[]>([]);

  useEffect(() => {
    if (!active || !enabled || !objectId) return;

    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setForbidden(false);
      try {
        const data = await auditoriaService.historicoObjeto(appLabel, modelName, objectId, {
          page_size: 50,
        });
        if (!cancelled) {
          setRegistros(data.results || []);
        }
      } catch (err) {
        if (cancelled) return;
        if (isApiForbidden(err) || getApiErrorStatus(err) === 403) {
          setForbidden(true);
          setError('Você não tem permissão para visualizar este histórico.');
        } else {
          setError(
            apiErrorMessage(err, {
              fallback: 'Não foi possível carregar o histórico. Tente novamente.',
            }),
          );
        }
        setRegistros([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [active, enabled, objectId, appLabel, modelName]);

  if (!enabled) {
    return null;
  }

  if (!objectId) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="auditoria-historico-sem-objeto">
        Salve o cadastro para consultar o histórico de alterações.
      </p>
    );
  }

  return (
    <div className="space-y-6" data-testid="auditoria-historico-panel">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Histórico de alterações</CardTitle>
          </div>
          <CardDescription className="text-xs" data-testid="auditoria-historico-escopo">
            {AUDITORIA_ESCOPO_TEXTO}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          {loading ? (
            <div
              className="flex items-center gap-2 text-sm text-muted-foreground py-4"
              data-testid="auditoria-historico-loading"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando histórico…
            </div>
          ) : null}

          {!loading && error ? (
            <div
              className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              role="alert"
              data-testid={forbidden ? 'auditoria-historico-forbidden' : 'auditoria-historico-erro'}
            >
              {error}
            </div>
          ) : null}

          {!loading && !error && registros.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2" data-testid="auditoria-historico-vazio">
              Nenhuma alteração registrada ainda.
            </p>
          ) : null}

          {!loading && !error && registros.length > 0 ? (
            <ol className="relative space-y-4 border-l border-border pl-5" data-testid="auditoria-historico-lista">
              {registros.map((reg) => (
                <ItemHistoricoAuditoria key={reg.id} reg={reg} />
              ))}

            </ol>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
