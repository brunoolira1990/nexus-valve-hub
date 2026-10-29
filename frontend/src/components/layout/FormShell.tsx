import { useState, type ReactNode } from 'react';
import { ArrowLeft, PanelRight } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { NexusButton } from '@/components/nexus';
import { StatusPipeline, type StatusStep } from '@/components/layout/StatusPipeline';
import { cn } from '@/lib/utils';

export interface FormShellAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'default' | 'outline';
  loading?: boolean;
  icon?: ReactNode;
}

export interface FormShellProps {
  titulo: string;
  subtitulo?: string;
  /**
   * Aceito por compatibilidade com a spec da sprint, mas ignorado de propósito:
   * o breadcrumb da página é responsabilidade do MainLayout (breadcrumbMap + Header),
   * e renderizá-lo aqui duplicava a trilha sob a barra de breadcrumb do shell.
   */
  breadcrumbs?: Array<{ label: string; path?: string }>;
  pipeline?: {
    steps: StatusStep[];
    currentKey: string;
    onChange?: (key: string) => void;
  };
  acoesPrincipais?: FormShellAction[];
  acoesSecundarias?: FormShellAction[];
  onVoltar?: () => void;
  somenteLeitura?: boolean;
  /** Formulário (coluna esquerda, ~70%). */
  children: ReactNode;
  /** Chatter/painel (coluna direita, ~30%, só em lg+ ou como drawer no mobile). */
  rail?: ReactNode;
  /** Default: true quando `rail` é fornecido. */
  mostrarRail?: boolean;
  /** Badges de contexto (status, empresa, ambiente fiscal). */
  meta?: ReactNode;
}

/**
 * Shell universal de telas de edição no padrão Odoo:
 * cabeçalho (título + ações + banda de pipeline opcional) fluindo no topo do
 * conteúdo, formulário à esquerda e rail de chatter/painel à direita.
 * Nada aqui reescreve PageHeader ou StatusPipeline; o shell apenas os embrulha
 * no layout de duas colunas que nenhuma tela tinha até a Sprint 3.13.
 */
export function FormShell({
  titulo,
  subtitulo,
  pipeline,
  acoesPrincipais = [],
  acoesSecundarias = [],
  onVoltar,
  somenteLeitura = false,
  children,
  rail,
  mostrarRail = rail != null,
  meta,
}: FormShellProps) {
  const [railAbertoMobile, setRailAbertoMobile] = useState(false);

  const acoes = (
    <div className="flex flex-wrap items-center gap-2">
      {onVoltar && (
        <NexusButton
          type="button"
          variant="outline"
          onClick={onVoltar}
          data-testid="form-shell-voltar"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Voltar
        </NexusButton>
      )}
      {!somenteLeitura &&
        acoesSecundarias.map((acao) => (
          <NexusButton
            key={acao.label}
            type="button"
            variant="outline"
            onClick={acao.onClick}
          >
            {acao.icon}
            {acao.label}
          </NexusButton>
        ))}
      {!somenteLeitura &&
        acoesPrincipais.map((acao) => (
          <NexusButton
            key={acao.label}
            type="button"
            // 'primary' no contrato do FormShell; a variante do shadcn chama-se 'default'.
            variant={acao.variant === 'primary' || !acao.variant ? 'default' : acao.variant}
            loading={acao.loading}
            onClick={acao.onClick}
          >
            {acao.icon}
            {acao.label}
          </NexusButton>
        ))}
    </div>
  );

  return (
    <div data-testid="form-shell" className="w-full">
      {/*
        O shell NÃO usa sticky: quem rola é o <main> do MainLayout e a barra de
        breadcrumb (Header) já fica pinada fora dele. O segundo sticky embrulhando o
        PageHeader colidia com o space-y do PageContainer e jogava o título para baixo.
        O breadcrumb do registro pertence ao MainLayout (breadcrumbMap), não ao PageHeader.
      */}
      <div data-testid="form-shell-header">
        <PageHeader title={titulo} description={subtitulo} badges={meta} actions={acoes} />
        {pipeline && (
          <div
            data-testid="form-shell-pipeline"
            className="-mt-2 border-t border-border/60 pt-3"
          >
            <StatusPipeline
              steps={pipeline.steps}
              currentKey={pipeline.currentKey}
              onChange={pipeline.onChange}
              somenteLeitura={somenteLeitura}
            />
          </div>
        )}
      </div>

      <div className="flex items-start gap-6 pb-6">
        <div data-testid="form-shell-content" className="min-w-0 flex-1">
          {children}
        </div>

        {mostrarRail && rail && (
          <>
            {/* Rail dentro da linha do conteúdo: o topo casa com o primeiro card, não com o header. */}
            <aside
              data-testid="form-shell-rail"
              className="hidden lg:block w-80 shrink-0 sticky top-4 self-start max-h-[calc(100vh-6rem)] overflow-y-auto border-l border-border pl-4"
            >
              {rail}
            </aside>

            {/* Mobile: o rail não ocupa a tela — vira um drawer aberto por botão flutuante. */}
            <button
              type="button"
              data-testid="form-shell-rail-toggle"
              onClick={() => setRailAbertoMobile(true)}
              className="lg:hidden fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-nexus-blue px-4 py-2.5 text-sm font-semibold text-white shadow-lg"
            >
              <PanelRight className="h-4 w-4" />
              Painel
            </button>
            {railAbertoMobile && (
              <div
                data-testid="form-shell-rail-drawer"
                className="lg:hidden fixed inset-0 z-50"
                role="dialog"
                aria-label="Painel"
              >
                <button
                  type="button"
                  aria-label="Fechar painel"
                  className="absolute inset-0 bg-black/40"
                  onClick={() => setRailAbertoMobile(false)}
                />
                <aside className={cn('absolute inset-y-0 right-0 w-[min(20rem,85vw)] bg-card border-l border-border p-4 overflow-y-auto shadow-xl')}>
                  {rail}
                </aside>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
