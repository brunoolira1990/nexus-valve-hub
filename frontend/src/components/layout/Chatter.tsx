import { useEffect, useState } from 'react';
import { Loader2, MessageSquare } from 'lucide-react';
import {
  HistoricoAlteracoesPanel,
  type HistoricoEscopo,
} from '@/components/auditoria/HistoricoAlteracoesPanel';
import { NexusButton } from '@/components/nexus';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { chatterNotasService, type NotaChatter } from '@/services/api/chatterNotas';
import { apiErrorMessage } from '@/services/api/config';

/**
 * Espelha `MODELOS_AUDITADOS` (backend/apps/auditoria/escopo.py). O valor de
 * `modelName` é o nome da classe em minúsculas, então família é
 * 'familiaproduto' — 'familia' devolve 404.
 */
const ESCOPOS_HISTORICO: Record<string, HistoricoEscopo> = {
  cliente: { appLabel: 'cadastros', modelName: 'cliente' },
  produto: { appLabel: 'produtos', modelName: 'produto' },
  familia: { appLabel: 'produtos', modelName: 'familiaproduto' },
};

function iniciaisAutor(nome: string | null): string {
  const partes = (nome ?? '').trim().split(/\s+/).filter(Boolean);
  const inicial = partes.slice(0, 2).map((parte) => parte[0]).join('');
  return (inicial || 'NX').toUpperCase();
}

function formatarDataLocal(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR');
  } catch {
    return iso;
  }
}

type Props = {
  entityType: string;
  entityId: number | null;
};

export function Chatter({ entityType, entityId }: Props) {
  const [notas, setNotas] = useState<NotaChatter[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erroLista, setErroLista] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);

  const escopo = ESCOPOS_HISTORICO[entityType];

  useEffect(() => {
    if (!entityId) {
      setNotas([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setCarregando(true);
      setErroLista(null);
      try {
        const data = await chatterNotasService.listar(entityType, entityId, { page_size: 50 });
        if (!cancelled) setNotas(data.results || []);
      } catch (err) {
        if (cancelled) return;
        setErroLista(
          apiErrorMessage(err, {
            fallback: 'Não foi possível carregar as notas. Tente novamente.',
          }),
        );
        setNotas([]);
      } finally {
        if (!cancelled) setCarregando(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entityType, entityId]);

  if (!entityId) {
    return (
      <div data-testid="chatter" className="space-y-4">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold tracking-tight">Chatter</h3>
        </div>
        <p
          className="text-sm text-muted-foreground"
          data-testid="chatter-sem-registro"
        >
          Salve o registro primeiro para ver o histórico e adicionar notas.
        </p>
      </div>
    );
  }

  async function enviarNota() {
    const textoNota = texto.trim();
    if (!textoNota || !entityId || enviando) return;
    setEnviando(true);
    setErroEnvio(null);
    try {
      const nota = await chatterNotasService.criar({
        entity_type: entityType,
        entity_id: entityId,
        texto: textoNota,
      });
      setNotas((atuais) => [nota, ...atuais]);
      setTexto('');
    } catch (err) {
      setErroEnvio(
        apiErrorMessage(err, { fallback: 'Não foi possível salvar a nota. Tente novamente.' }),
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div data-testid="chatter" className="space-y-3">
      <div className="flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold tracking-tight">Chatter</h3>
      </div>

      <Tabs defaultValue="historico" data-testid="chatter-tabs">
        <TabsList className="w-full">
          <TabsTrigger value="historico">Histórico</TabsTrigger>
          <TabsTrigger value="notas">Notas internas</TabsTrigger>
          <TabsTrigger value="atividades">Atividades</TabsTrigger>
        </TabsList>

        <TabsContent value="historico" className="space-y-3">
          {escopo ? (
            <HistoricoAlteracoesPanel {...escopo} objectId={entityId} />
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="chatter-historico-indisponivel">
              Histórico de alterações indisponível para este registro.
            </p>
          )}
        </TabsContent>

        <TabsContent value="notas" className="space-y-4">
          <div className="space-y-3">
            <Textarea
              value={texto}
              onChange={(event) => setTexto(event.target.value)}
              placeholder="Deixe uma nota interna…"
              rows={3}
              aria-label="Nova nota interna"
              data-testid="chatter-notas-composer"
            />
            {erroEnvio ? (
              <div
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {erroEnvio}
              </div>
            ) : null}
            <div className="flex justify-end">
              <NexusButton
                onClick={enviarNota}
                disabled={!texto.trim() || enviando}
                data-testid="chatter-notas-enviar"
              >
                {enviando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Enviar
              </NexusButton>
            </div>
          </div>

          {carregando ? (
            <div
              className="flex items-center gap-2 text-sm text-muted-foreground"
              data-testid="chatter-notas-loading"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando notas…
            </div>
          ) : null}

          {!carregando && erroLista ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {erroLista}
            </div>
          ) : null}

          {!carregando && !erroLista && notas.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="chatter-notas-vazio">
              Nenhuma nota interna ainda.
            </p>
          ) : null}

          {!carregando && !erroLista && notas.length > 0 ? (
            <ol
              className="space-y-3 border-l border-border pl-4"
              data-testid="chatter-notas-lista"
            >
              {notas.map((nota) => (
                <li key={nota.id} className="relative" data-testid={`chatter-nota-${nota.id}`}>
                  <span
                    aria-hidden
                    className="absolute -left-[22px] top-1 h-2 w-2 rounded-full border-2 border-background bg-primary/70"
                  />
                  <div className="flex items-start gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback>{iniciaisAutor(nota.autor_nome)}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm font-medium">{nota.autor_nome || 'Usuário removido'}</p>
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {formatarDataLocal(nota.criado_em)}
                        </span>
                      </div>
                      <p className="mt-0.5 whitespace-pre-wrap text-sm text-muted-foreground">
                        {nota.texto}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : null}
        </TabsContent>

        <TabsContent value="atividades">
          <p className="text-sm text-muted-foreground" data-testid="chatter-atividades-breve">
            Em breve (Sprint 3.15).
          </p>
        </TabsContent>
      </Tabs>
    </div>
  );
}
