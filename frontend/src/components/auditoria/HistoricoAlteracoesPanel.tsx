import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  AUDITORIA_ESCOPO_TEXTO,
  AUDITORIA_VALOR_PROTEGIDO,
  campoEhProtegido,
  entradasAlteracao,
  formatarValorAuditoria,
  labelCampoAuditoria,
  labelOperacaoAuditoria,
} from '@/lib/auditoriaHistorico';
import {
  auditoriaService,
  type RegistroAuditoria,
} from '@/services/api/auditoria';
import { apiErrorMessage, getApiErrorStatus, isApiForbidden } from '@/services/api/config';

type Props = {
  appLabel: 'cadastros' | 'produtos';
  modelName: 'cliente' | 'produto';
  objectId?: number | null;
  active?: boolean;
  enabled?: boolean;
};

function formatarDataLocal(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR');
  } catch {
    return iso;
  }
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
    <div className="space-y-3" data-testid="auditoria-historico-panel">
      <p className="text-sm text-muted-foreground" data-testid="auditoria-historico-escopo">
        {AUDITORIA_ESCOPO_TEXTO}
      </p>

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
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
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
        <ul className="space-y-3" data-testid="auditoria-historico-lista">
          {registros.map((reg) => (
            <li
              key={reg.id}
              className="rounded-md border border-border bg-muted/20 px-3 py-3"
              data-testid={`auditoria-evento-${reg.id}`}
              data-operacao={reg.operacao}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium">{labelOperacaoAuditoria(reg.operacao)}</p>
                <p className="text-xs text-muted-foreground">{formatarDataLocal(reg.criado_em)}</p>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Por: {reg.ator?.nome || 'Sistema / usuário removido'}
              </p>
              <ul className="mt-2 space-y-1.5">
                {entradasAlteracao(reg).map(({ campo, alt }) => (
                  <li key={campo} className="text-sm" data-testid={`auditoria-campo-${campo}`}>
                    <span className="font-medium">{labelCampoAuditoria(campo)}</span>
                    {campoEhProtegido(alt) ? (
                      <span className="text-muted-foreground"> — {AUDITORIA_VALOR_PROTEGIDO}</span>
                    ) : (
                      <span className="text-muted-foreground">
                        {' '}
                        — de {formatarValorAuditoria('antes' in alt ? alt.antes : null)} para{' '}
                        {formatarValorAuditoria('depois' in alt ? alt.depois : null)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
