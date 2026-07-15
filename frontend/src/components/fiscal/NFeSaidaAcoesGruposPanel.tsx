import {
  ClipboardCheck,
  Copy,
  Download,
  ExternalLink,
  FileCode,
  FileText,
  History,
  Loader2,
  Mail,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  GRUPO_ACAO_LABELS,
  agruparAcoesPorGrupo,
  type NFeSaidaAcaoConfig,
  type NFeSaidaContextoAcao,
} from '@/lib/nfeSaidaAcoesMatriz';

type Props = {
  contexto: NFeSaidaContextoAcao;
  acoes: NFeSaidaAcaoConfig[];
  danfeLoading?: boolean;
  baixarDanfeLoading?: boolean;
  onValidar?: () => void;
  onAbrirNfe?: () => void;
  onHistorico?: () => void;
  onDanfe?: () => void;
  onBaixarDanfe?: () => void;
  onXml?: () => void;
  onXmlAutorizado?: () => void;
  onCopiarChave?: () => void;
  onDescartar?: () => void;
  onConsultaSefaz?: () => void;
  consultaSefazLoading?: boolean;
  onCartaCorrecao?: () => void;
  cartaCorrecaoLoading?: boolean;
  onCancelamento?: () => void;
  onInutilizacao?: () => void;
  onEnvioDanfeXml?: () => void;
  financeiroSlot?: React.ReactNode;
  compact?: boolean;
};

function GrupoSecao({
  titulo,
  children,
  compact,
}: {
  titulo: string;
  children: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <section className={compact ? 'space-y-1.5' : 'space-y-2'}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{titulo}</p>
      <div className="flex flex-wrap gap-2">{children}</div>
    </section>
  );
}

function BotaoAcao({
  acao,
  onClick,
  href,
  loading,
  variant = 'outline',
  children,
}: {
  acao: NFeSaidaAcaoConfig;
  onClick?: () => void;
  href?: string;
  loading?: boolean;
  variant?: 'outline' | 'primary' | 'destructive';
  children?: React.ReactNode;
}) {
  const cls =
    variant === 'primary'
      ? 'erp-btn-primary erp-btn-sm'
      : variant === 'destructive'
        ? 'erp-btn-outline erp-btn-sm text-destructive border-destructive/40'
        : acao.futura || !acao.habilitada
          ? 'erp-btn-outline erp-btn-sm opacity-50 cursor-not-allowed'
          : 'erp-btn-outline erp-btn-sm';

  const disabled = acao.futura || !acao.habilitada || loading;
  const title = acao.title || (acao.futura ? 'Disponível em fase futura' : undefined);
  const label = (
    <>
      {children}
      {acao.label}
    </>
  );

  if (href && acao.habilitada && !acao.futura) {
    return (
      <a className={cls} href={href} target="_blank" rel="noreferrer" title={title}>
        {label}
      </a>
    );
  }

  return (
    <button type="button" className={cls} disabled={disabled} title={title} onClick={onClick}>
      {loading ? <Loader2 className="h-3 w-3 animate-spin inline mr-1" /> : null}
      {label}
    </button>
  );
}

export function NFeSaidaAcoesContextoBanner({ contexto }: { contexto: NFeSaidaContextoAcao }) {
  const ambienteClass = contexto.cancelada
    ? 'border-destructive/40 bg-destructive/5 text-destructive'
    : contexto.autorizadaProducao
      ? 'border-red-600/40 bg-red-950/5 text-red-800 dark:text-red-300'
      : contexto.autorizadaHomolog
        ? 'border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100'
        : 'border-border bg-muted/20 text-muted-foreground';

  return (
    <div className={`rounded-md border px-3 py-2 space-y-1 text-xs ${ambienteClass}`}>
      <p>
        <span className="font-medium">Ambiente:</span> {contexto.ambienteLabel}
        {contexto.cancelada ? (
          <span className="ml-2 erp-badge-danger text-[10px]">Cancelada</span>
        ) : null}
        {contexto.autorizadaHomolog ? (
          <span className="ml-2 erp-badge-warning text-[10px]">Sem valor fiscal</span>
        ) : null}
        {contexto.autorizadaProducao ? (
          <span className="ml-2 erp-badge-success text-[10px]">Produção SEFAZ</span>
        ) : null}
      </p>
      {contexto.avisoAmbiente ? <p>{contexto.avisoAmbiente}</p> : null}
    </div>
  );
}

export function NFeSaidaAcoesGruposPanel({
  contexto,
  acoes,
  danfeLoading,
  baixarDanfeLoading,
  onValidar,
  onAbrirNfe,
  onHistorico,
  onDanfe,
  onBaixarDanfe,
  onXml,
  onDescartar,
  onConsultaSefaz,
  consultaSefazLoading,
  onCartaCorrecao,
  cartaCorrecaoLoading,
  onCancelamento,
  onInutilizacao,
  onEnvioDanfeXml,
  onXmlAutorizado,
  financeiroSlot,
  compact,
}: Props) {
  const grupos = agruparAcoesPorGrupo(acoes);

  const copiarChave = () => {
    if (!contexto.chaveAcesso) return;
    void navigator.clipboard.writeText(contexto.chaveAcesso).then(() => {
      toast.success('Chave de acesso copiada.');
    });
  };

  const renderAcao = (acao: NFeSaidaAcaoConfig) => {
    switch (acao.id) {
      case 'validar':
        return (
          <button key={acao.id} type="button" className="erp-btn-outline erp-btn-sm" onClick={onValidar}>
            <ClipboardCheck className="h-3 w-3 mr-1 inline" />
            {acao.label}
          </button>
        );
      case 'abrir_nfe':
        return (
          <button key={acao.id} type="button" className="erp-btn-primary erp-btn-sm" onClick={onAbrirNfe}>
            <ExternalLink className="h-3 w-3 mr-1 inline" />
            {acao.label}
          </button>
        );
      case 'historico':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={onHistorico ?? onAbrirNfe}
          >
            <History className="h-3 w-3 mr-1 inline" />
            {acao.label}
          </button>
        );
      case 'danfe_previa':
      case 'danfe_autorizado':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={danfeLoading || !acao.habilitada}
            onClick={onDanfe}
          >
            {danfeLoading ? (
              <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
            ) : (
              <FileText className="h-3 w-3 mr-1 inline" />
            )}
            {acao.label}
          </button>
        );
      case 'baixar_danfe':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={baixarDanfeLoading || danfeLoading || !acao.habilitada}
            onClick={onBaixarDanfe}
          >
            {baixarDanfeLoading ? (
              <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
            ) : (
              <Download className="h-3 w-3 mr-1 inline" />
            )}
            {acao.label}
          </button>
        );
      case 'xml_previo':
        return (
          <button key={acao.id} type="button" className="erp-btn-outline erp-btn-sm" onClick={onXml}>
            <FileCode className="h-3 w-3 mr-1 inline" />
            {acao.label}
          </button>
        );
      case 'xml_autorizado':
        return (
          <BotaoAcao key={acao.id} acao={acao} onClick={onXmlAutorizado ?? onXml}>
            <FileCode className="h-3 w-3 mr-1 inline" />
          </BotaoAcao>
        );
      case 'copiar_chave':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={!acao.habilitada}
            title={acao.title}
            onClick={copiarChave}
          >
            <Copy className="h-3 w-3 mr-1 inline" />
            {acao.label}
          </button>
        );
      case 'descartar_rascunho':
        return <BotaoAcao key={acao.id} acao={acao} variant="destructive" onClick={onDescartar} />;
      case 'consulta_sefaz':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={!acao.habilitada || consultaSefazLoading}
            title={acao.title}
            onClick={onConsultaSefaz}
          >
            {consultaSefazLoading ? <Loader2 className="h-3 w-3 animate-spin inline mr-1" /> : null}
            {acao.label}
          </button>
        );
      case 'carta_correcao':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={!acao.habilitada || cartaCorrecaoLoading}
            title={acao.title}
            onClick={onCartaCorrecao}
          >
            {cartaCorrecaoLoading ? <Loader2 className="h-3 w-3 animate-spin inline mr-1" /> : null}
            {acao.label}
          </button>
        );
      case 'cancelamento':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-destructive erp-btn-sm"
            disabled={!acao.habilitada}
            title={acao.title}
            onClick={onCancelamento}
          >
            {acao.label}
          </button>
        );
      case 'inutilizacao':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-destructive erp-btn-sm"
            disabled={!acao.habilitada}
            title={acao.title}
            onClick={onInutilizacao}
          >
            {acao.label}
          </button>
        );
      case 'enviar_danfe_xml':
        return (
          <button
            key={acao.id}
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={!acao.habilitada}
            title={acao.title}
            onClick={onEnvioDanfeXml}
          >
            <Mail className="h-3 w-3 mr-1 inline" />
            {acao.label}
          </button>
        );
      default:
        return <BotaoAcao key={acao.id} acao={acao} />;
    }
  };

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      <NFeSaidaAcoesContextoBanner contexto={contexto} />
      {grupos.fiscal.length ? (
        <GrupoSecao titulo={GRUPO_ACAO_LABELS.fiscal} compact={compact}>
          {grupos.fiscal.map(renderAcao)}
        </GrupoSecao>
      ) : null}
      {grupos.documentos.length ? (
        <GrupoSecao titulo={GRUPO_ACAO_LABELS.documentos} compact={compact}>
          {grupos.documentos.map(renderAcao)}
        </GrupoSecao>
      ) : null}
      {financeiroSlot || contexto.autorizadaHomolog ? (
        <section className={compact ? 'space-y-1.5' : 'space-y-2'}>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {GRUPO_ACAO_LABELS.financeiras}
          </p>
          {financeiroSlot}
          {contexto.autorizadaHomolog && !financeiroSlot ? (
            <p className="text-xs text-muted-foreground">Financeiro indisponível para NF-e de homologação.</p>
          ) : null}
        </section>
      ) : null}
      {grupos.futuras.length ? (
        <GrupoSecao titulo={GRUPO_ACAO_LABELS.futuras} compact={compact}>
          {grupos.futuras.map((a) => (
            <BotaoAcao key={a.id} acao={a} />
          ))}
        </GrupoSecao>
      ) : null}
    </div>
  );
}
