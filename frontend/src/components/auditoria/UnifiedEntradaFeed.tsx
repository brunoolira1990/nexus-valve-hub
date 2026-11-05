import { useEffect, useState } from 'react';
import { History, Loader2 } from 'lucide-react';
import {
  ItemHistoricoAuditoria,
} from '@/components/auditoria/HistoricoAlteracoesPanel';
import { AUDITORIA_ESCOPO_TEXTO } from '@/lib/auditoriaHistorico';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  auditoriaService,
  type AuditoriaHistoricoResponse,
  type RegistroAuditoria,
} from '@/services/api/auditoria';
import { apiErrorMessage, getApiErrorStatus, isApiForbidden } from '@/services/api/config';

/**
 * Feed unificado do documento de entrada (PR 4 da Fase 1).
 *
 * A conferência NF-e vive em DUAS entidades auditadas: a conferência em si
 * (`NFeEntradaConferencia`, dados.id) e a nota histórica importada
 * (`NFeEntradaHistoricaImportada`, pk da URL). O financeiro (gerar_contas_pagar /
 * estornar_contas) é gravado contra a HISTÓRICA (contrato do PR 3), então um rail
 * que consulta só a conferência escondia esses eventos. Este componente consulta
 * as duas fontes pelo MESMO caminho do Chatter (auditoriaService.historicoObjeto),
 * mescla por criado_em e renderiza com o renderer do PR 2 extraído para
 * ItemHistoricoAuditoria — sem duplicar o parser de EVENTO/diff.
 */

/** Pares idênticos a MODELOS_AUDITADOS (backend/apps/auditoria/escopo.py). */
const ESCOPO_CONFERENCIA = {
  appLabel: 'fiscal',
  modelName: 'nfeentradaconferencia',
} as const;

const ESCOPO_HISTORICA = {
  appLabel: 'fiscal',
  modelName: 'nfeentradahistoricaimportada',
} as const;

type Fonte = 'conferencia' | 'historica';

type EstadoFonte = {
  carregando: boolean;
  erro: string | null;
  proibido: boolean;
  registros: RegistroAuditoria[];
};

const ESTADO_INICIAL: EstadoFonte = {
  carregando: false,
  erro: null,
  proibido: false,
  registros: [],
};

type Props = {
  /** PK da NFeEntradaConferencia (dados.id da resposta do painel); null = ainda não salva. */
  conferenceId: number | null;
  /** PK da NFeEntradaHistoricaImportada (nfId da URL). */
  historicaId: number | null;
};

/**
 * Busca de uma fonte. O panel histórico tem a mesma regra: page_size 50 e
 * bandeira de cancelamento para a resposta antiga não sobrescrever a troca de id.
 */
function useFonteAuditada(
  fonte: Fonte,
  escopo: { appLabel: string; modelName: string },
  objectId: number | null,
): EstadoFonte {
  const [estado, setEstado] = useState<EstadoFonte>(ESTADO_INICIAL);

  useEffect(() => {
    if (!objectId) {
      setEstado(ESTADO_INICIAL);
      return;
    }
    let cancelled = false;
    (async () => {
      setEstado({ ...ESTADO_INICIAL, carregando: true });
      try {
        const data: AuditoriaHistoricoResponse = await auditoriaService.historicoObjeto(
          escopo.appLabel,
          escopo.modelName,
          objectId,
          { page_size: 50 },
        );
        if (cancelled) return;
        setEstado({
          carregando: false,
          erro: null,
          proibido: false,
          registros: data.results || [],
        });
      } catch (err) {
        if (cancelled) return;
        const proibido = isApiForbidden(err) || getApiErrorStatus(err) === 403;
        setEstado({
          carregando: false,
          proibido,
          registros: [],
          erro: proibido
            ? `Você não tem permissão para visualizar o histórico (${fonte}).`
            : apiErrorMessage(err, {
                fallback: `Não foi possível carregar o histórico (${fonte}). Tente novamente.`,
              }),
        });
      }
    })();

    return () => {
      cancelled = true;
    };
    // escopo é constante por fonte; objectId é o gatilho real.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fonte, objectId]);

  return estado;
}

type ItemFeed = RegistroAuditoria & { fonte: Fonte };

function compararPorCriadoEmDesc(a: ItemFeed, b: ItemFeed): number {
  const porData = b.criado_em.localeCompare(a.criado_em);
  if (porData !== 0) return porData;
  // id é global na tabela de auditoria, então o desempate nunca colide entre fontes.
  return b.id - a.id;
}

export function UnifiedEntradaFeed({ conferenceId, historicaId }: Props) {
  const conferencia = useFonteAuditada('conferencia', ESCOPO_CONFERENCIA, conferenceId);
  const historica = useFonteAuditada('historica', ESCOPO_HISTORICA, historicaId);

  const carregando = conferencia.carregando || historica.carregando;
  const itens: ItemFeed[] = [
    ...conferencia.registros.map((reg) => ({ ...reg, fonte: 'conferencia' as const })),
    ...historica.registros.map((reg) => ({ ...reg, fonte: 'historica' as const })),
  ].sort(compararPorCriadoEmDesc);

  const nenhumaId = conferenceId === null && historicaId === null;

  return (
    <div className="space-y-6" data-testid="auditoria-feed-panel">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Histórico do documento</CardTitle>
          </div>
          <CardDescription className="text-xs" data-testid="auditoria-feed-escopo">
            {AUDITORIA_ESCOPO_TEXTO}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          {nenhumaId ? (
            <p
              className="text-sm text-muted-foreground"
              data-testid="auditoria-feed-sem-objeto"
            >
              Salve o registro para consultar o histórico de alterações.
            </p>
          ) : null}

          {carregando ? (
            <div
              className="flex items-center gap-2 text-sm text-muted-foreground py-4"
              data-testid="auditoria-feed-loading"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando histórico…
            </div>
          ) : null}

          {/* Degradação por fonte: a falha de uma não esconde a outra. */}
          {conferenceId && !conferencia.carregando && conferencia.erro ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              data-testid={
                conferencia.proibido
                  ? 'auditoria-feed-forbidden-conferencia'
                  : 'auditoria-feed-erro-conferencia'
              }
            >
              {conferencia.erro}
            </div>
          ) : null}

          {historicaId && !historica.carregando && historica.erro ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              data-testid={
                historica.proibido
                  ? 'auditoria-feed-forbidden-historica'
                  : 'auditoria-feed-erro-historica'
              }
            >
              {historica.erro}
            </div>
          ) : null}

          {!carregando &&
          !conferencia.erro &&
          !historica.erro &&
          itens.length === 0 &&
          !nenhumaId ? (
            <p
              className="text-sm text-muted-foreground py-2"
              data-testid="auditoria-feed-vazio"
            >
              Nenhuma alteração registrada ainda.
            </p>
          ) : null}

          {!carregando && itens.length > 0 ? (
            <ol
              className="relative space-y-4 border-l border-border pl-5"
              data-testid="auditoria-feed-lista"
            >
              {/* O id de RegistroAuditoria é global (uma única tabela), então as
                  linhas mescladas nunca colidem entre as duas fontes. */}
              {itens.map((item) => (
                <ItemHistoricoAuditoria key={`${item.fonte}-${item.id}`} reg={item} />
              ))}
            </ol>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
