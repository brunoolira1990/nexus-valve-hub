import { useEffect, useRef, useState } from 'react';
import { Loader2, MessageSquare, Paperclip, X } from 'lucide-react';
import {
  HistoricoAlteracoesPanel,
  type HistoricoEscopo,
} from '@/components/auditoria/HistoricoAlteracoesPanel';
import { NexusButton } from '@/components/nexus';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useAppContexto } from '@/hooks/useAppContexto';
import {
  chatterNotasService,
  type AnexoChatter,
  type NotaChatter,
} from '@/services/api/chatterNotas';
import { apiErrorMessage } from '@/services/api/config';

/**
 * Espelha `ANEXO_EXTENSOES_PERMITIDAS` (backend/apps/chatter/serializers.py). É só o
 * `accept` do seletor: a validação que vale é a do backend.
 */
const ANEXO_ACCEPT = '.pdf,.png,.jpg,.jpeg,.xml,.csv,.docx,.xlsx';

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

function formatarTamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
  const { contexto } = useAppContexto();
  const [notas, setNotas] = useState<NotaChatter[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erroLista, setErroLista] = useState<string | null>(null);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [pendentes, setPendentes] = useState<File[]>([]);
  const [erroAnexo, setErroAnexo] = useState<string | null>(null);
  const [excluindoAnexoId, setExcluindoAnexoId] = useState<number | null>(null);
  const [anexoConfirmar, setAnexoConfirmar] = useState<AnexoChatter | null>(null);
  const inputArquivoRef = useRef<HTMLInputElement>(null);
  // Resposta mais antiga não pode sobrescrever a lista depois de trocar de registro.
  const requisicaoRef = useRef(0);

  const escopo = ESCOPOS_HISTORICO[entityType];

  async function carregarNotas() {
    if (!entityId) return;
    const sequencia = ++requisicaoRef.current;
    setCarregando(true);
    setErroLista(null);
    try {
      const data = await chatterNotasService.listar(entityType, entityId, { page_size: 50 });
      if (requisicaoRef.current === sequencia) setNotas(data.results || []);
    } catch (err) {
      if (requisicaoRef.current !== sequencia) return;
      setErroLista(
        apiErrorMessage(err, {
          fallback: 'Não foi possível carregar as notas. Tente novamente.',
        }),
      );
      setNotas([]);
    } finally {
      if (requisicaoRef.current === sequencia) setCarregando(false);
    }
  }

  useEffect(() => {
    if (!entityId) {
      setNotas([]);
      return;
    }
    void carregarNotas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, entityId]);

  function selecionarArquivos(files: FileList | null) {
    const novos = Array.from(files ?? []);
    if (!novos.length) return;
    setPendentes((atuais) => [...atuais, ...novos]);
  }

  function removerPendente(indice: number) {
    setPendentes((atuais) => {
      const restantes = atuais.filter((_, i) => i !== indice);
      if (!restantes.length && inputArquivoRef.current) inputArquivoRef.current.value = '';
      return restantes;
    });
  }

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

  /**
   * Espelha `AnexoChatterViewSet.perform_destroy`: autor da nota ou superuser.
   * É pré-filtro de UI (não mostra botão inútil); a autoridade continua o backend.
   */
  function podeExcluirAnexo(nota: NotaChatter): boolean {
    const usuario = contexto.usuario;
    if (!usuario.id) return false;
    return Boolean(usuario.is_superuser) || nota.autor === usuario.id;
  }

  async function excluirAnexoGravado(anexo: AnexoChatter) {
    if (excluindoAnexoId !== null) return;
    setExcluindoAnexoId(anexo.id);
    setErroAnexo(null);
    try {
      await chatterNotasService.excluirAnexo(anexo.id);
      await carregarNotas();
    } catch (err) {
      const detalhe = apiErrorMessage(err, { fallback: 'Tente novamente.' });
      setErroAnexo(`Não foi possível excluir ${anexo.nome_original}: ${detalhe}`);
    } finally {
      setExcluindoAnexoId(null);
    }
  }

  function abrirConfirmacaoAnexo(anexo: AnexoChatter) {
    if (excluindoAnexoId !== null) return;
    setErroAnexo(null);
    setAnexoConfirmar(anexo);
  }

  function confirmarExclusaoAnexo() {
    if (!anexoConfirmar) return;
    const anexo = anexoConfirmar;
    // Fecha antes de disparar: o diálogo é uma pergunta, não um painel de progresso.
    setAnexoConfirmar(null);
    void excluirAnexoGravado(anexo);
  }

  async function enviarNota() {
    const textoNota = texto.trim();
    if (!textoNota || !entityId || enviando) return;
    setEnviando(true);
    setErroEnvio(null);
    const haveriaUpload = pendentes.length > 0;
    try {
      const nota = await chatterNotasService.criar({
        entity_type: entityType,
        entity_id: entityId,
        texto: textoNota,
      });
      setNotas((atuais) => [nota, ...atuais]);
      setTexto('');

      const falhas: string[] = [];
      for (const arquivo of pendentes) {
        try {
          await chatterNotasService.uploadAnexo(nota.id, arquivo);
        } catch (err) {
          falhas.push(`${arquivo.name}: ${apiErrorMessage(err, { fallback: 'falha no envio.' })}`);
        }
      }
      setPendentes([]);
      if (inputArquivoRef.current) inputArquivoRef.current.value = '';

      if (falhas.length) {
        setErroEnvio(`A nota foi salva, mas o anexo não: ${falhas.join(' | ')}`);
      }
      if (haveriaUpload) await carregarNotas();
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
            <input
              ref={inputArquivoRef}
              type="file"
              multiple
              accept={ANEXO_ACCEPT}
              className="hidden"
              aria-label="Selecionar anexos da nota"
              data-testid="chatter-anexo-input"
              onChange={(event) => selecionarArquivos(event.target.files)}
            />
            <Textarea
              value={texto}
              onChange={(event) => setTexto(event.target.value)}
              placeholder="Deixe uma nota interna…"
              rows={3}
              aria-label="Nova nota interna"
              data-testid="chatter-notas-composer"
            />

            {pendentes.length > 0 ? (
              <ul className="space-y-1" data-testid="chatter-anexos-pendentes">
                {pendentes.map((arquivo, indice) => (
                  <li
                    key={`${arquivo.name}-${indice}`}
                    className="flex items-center justify-between gap-2 text-xs text-muted-foreground"
                    data-testid={`chatter-anexo-pendente-${indice}`}
                  >
                    <span className="min-w-0 truncate">
                      {arquivo.name} · {formatarTamanho(arquivo.size)}
                    </span>
                    <button
                      type="button"
                      onClick={() => removerPendente(indice)}
                      aria-label={`Remover ${arquivo.name}`}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            {erroEnvio ? (
              <div
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {erroEnvio}
              </div>
            ) : null}

            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <NexusButton
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => inputArquivoRef.current?.click()}
                  data-testid="chatter-anexo-botao"
                >
                  <Paperclip className="mr-2 h-4 w-4" />
                  Anexar
                </NexusButton>
                {pendentes.length > 0 ? (
                  <span
                    className="text-xs text-muted-foreground"
                    data-testid="chatter-anexo-contador"
                  >
                    {pendentes.length} anexo{pendentes.length > 1 ? 's' : ''}
                  </span>
                ) : null}
              </div>
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

          {!carregando && erroAnexo ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              data-testid="chatter-anexo-erro"
            >
              {erroAnexo}
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

                      {nota.anexos.length > 0 ? (
                        <ul className="mt-2 space-y-1" data-testid={`chatter-nota-anexos-${nota.id}`}>
                          {nota.anexos.map((anexo) => (
                            <li key={anexo.id} className="flex items-center gap-1">
                              <a
                                href={anexo.arquivo_url}
                                download={anexo.nome_original}
                                className="inline-flex min-w-0 items-center gap-1.5 text-xs text-nexus-blue hover:underline"
                                data-testid={`chatter-anexo-${anexo.id}`}
                              >
                                <Paperclip className="h-3.5 w-3.5" aria-hidden />
                                <span className="min-w-0 truncate">{anexo.nome_original}</span>
                                <span className="text-muted-foreground">
                                  · {formatarTamanho(anexo.tamanho_bytes)}
                                </span>
                              </a>
                              {podeExcluirAnexo(nota) ? (
                                <button
                                  type="button"
                                  onClick={() => abrirConfirmacaoAnexo(anexo)}
                                  disabled={excluindoAnexoId !== null}
                                  aria-label={`Excluir ${anexo.nome_original}`}
                                  data-testid={`chatter-anexo-excluir-${anexo.id}`}
                                  className="shrink-0 text-muted-foreground transition-colors hover:text-destructive"
                                >
                                  {excluindoAnexoId === anexo.id ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                                  ) : (
                                    <X className="h-3.5 w-3.5" aria-hidden />
                                  )}
                                </button>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : null}
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

      {anexoConfirmar ? (
        <Dialog
          open
          onOpenChange={(aberto) => {
            if (!aberto) setAnexoConfirmar(null);
          }}
        >
          <DialogContent className="sm:max-w-md" data-testid="chatter-confirmar-anexo">
            <DialogHeader>
              <DialogTitle>Excluir anexo?</DialogTitle>
              <DialogDescription>
                O arquivo "{anexoConfirmar.nome_original}" será removido permanentemente.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <NexusButton
                type="button"
                variant="outline"
                onClick={() => setAnexoConfirmar(null)}
                data-testid="chatter-anexo-cancelar"
              >
                Cancelar
              </NexusButton>
              <NexusButton
                type="button"
                variant="destructive"
                onClick={confirmarExclusaoAnexo}
                data-testid="chatter-anexo-confirmar"
              >
                Excluir
              </NexusButton>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}
