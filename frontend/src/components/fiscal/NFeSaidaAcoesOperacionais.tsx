import { Loader2, Copy } from 'lucide-react';
import { AdvancedSupportSection } from '@/components/nexus/AdvancedSupportSection';
import { OperationalMessage } from '@/components/nexus/OperationalMessage';
import { ACTION_LABELS, TECHNICAL_DOWNLOAD_LABELS, labelNfeStatusConferenciaOperacional } from '@/lib/operationalUi';
import { AVISO_HOMOLOG_SEM_VALOR_FISCAL, AVISO_CANCELADA_CONSULTA, deveUsarDanfeAutorizado } from '@/lib/nfeSaidaAcoesMatriz';
import { openBlobInNewTab } from '@/lib/downloadBlobFile';
import { formatNfeXsdErro } from '@/lib/nfeXsdErros';
import {
  nfeSaidasService,
  type DanfePreviewMeta,
  type NFeSaidaPreviewXmlResponse,
} from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { toast } from 'sonner';

type EmissaoSefaz = {
  status_emissao_sefaz?: string;
  tem_xml_nfe_gerado?: boolean;
  tem_xml_assinado?: boolean;
  tem_xml_envio_lote?: boolean;
  tem_xml_retorno?: boolean;
  tem_xml_autorizado?: boolean;
  chave_acesso?: string;
  protocolo_autorizacao?: string;
  autorizada_em?: string | null;
  nfe?: { cstat?: string; xmotivo?: string; protocolo?: string };
};

type Props = {
  nfeId: number;
  autorizadaHomolog: boolean;
  autorizadaProducao?: boolean;
  cancelada?: boolean;
  statusConferencia?: string | null;
  emissaoLoading: boolean;
  danfeLoading: boolean;
  validarXmlLoading: boolean;
  podeTentarEmitirHomolog: boolean;
  podeEmitirHomolog: boolean;
  labelEmitir: string;
  emissaoSefaz?: EmissaoSefaz | null;
  danfeMeta?: DanfePreviewMeta | null;
  validacaoXsdErros: Array<Record<string, unknown>>;
  onEmitir: () => void;
  onValidarXmlLocal: () => void;
  onPreviewError: (msg: string | null) => void;
  onDanfeMeta: (meta: DanfePreviewMeta | undefined) => void;
  onDanfeLoading: (v: boolean) => void;
  onXmlPreview: (payload: NFeSaidaPreviewXmlResponse) => void;
  onXmlModalOpen: (v: boolean) => void;
  children?: React.ReactNode;
};

export function NFeSaidaAcoesOperacionais({
  nfeId,
  autorizadaHomolog,
  autorizadaProducao = false,
  cancelada = false,
  statusConferencia,
  emissaoLoading,
  danfeLoading,
  validarXmlLoading,
  podeTentarEmitirHomolog,
  podeEmitirHomolog,
  labelEmitir,
  emissaoSefaz,
  danfeMeta,
  validacaoXsdErros,
  onEmitir,
  onValidarXmlLocal,
  onPreviewError,
  onDanfeMeta,
  onDanfeLoading,
  onXmlPreview,
  onXmlModalOpen,
  children,
}: Props) {
  const abrirDanfe = async () => {
    onPreviewError(null);
    onDanfeLoading(true);
    try {
      const usarAutorizado = deveUsarDanfeAutorizado({
        autorizadaHomolog,
        autorizadaProducao,
        cancelada,
        temXmlAutorizado: Boolean(emissaoSefaz?.tem_xml_autorizado),
      });
      if (usarAutorizado) {
        const { blob, filename } = await nfeSaidasService.danfeAutorizadoBlob(nfeId);
        const abriu = openBlobInNewTab(blob, filename);
        if (!abriu) {
          toast.info('Download do DANFE iniciado (pop-up bloqueado pelo navegador).');
        }
        return;
      }
      const { blob, meta } = await nfeSaidasService.previewDanfeBlob(nfeId);
      onDanfeMeta(meta);
      const u = URL.createObjectURL(blob);
      window.open(u, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(u), 60_000);
    } catch (err) {
      onPreviewError(
        apiErrorMessage(err, {
          fallback: 'Não foi possível gerar o DANFE. A nota não foi alterada. Tente novamente ou acione o suporte.',
        }),
      );
    } finally {
      onDanfeLoading(false);
    }
  };

  const baixarXmlAutorizado = async () => {
    try {
      await nfeSaidasService.downloadXmlAutorizado(nfeId);
    } catch (err) {
      onPreviewError(
        apiErrorMessage(err, { fallback: 'Não foi possível baixar o XML autorizado.' }),
      );
    }
  };

  const statusLabel = labelNfeStatusConferenciaOperacional(
    emissaoSefaz?.status_emissao_sefaz,
    statusConferencia,
  );
  const autorizada = autorizadaHomolog || autorizadaProducao;
  const documentoAutorizadoLocal = Boolean(emissaoSefaz?.tem_xml_autorizado);

  return (
    <div className="space-y-3">
      {cancelada ? (
        <OperationalMessage
          title="NF-e cancelada"
          message={AVISO_CANCELADA_CONSULTA}
          variant="error"
          raw
        />
      ) : null}

      {!autorizada && !cancelada ? (
        <OperationalMessage
          title={`Status: ${statusLabel}`}
          message={
            emissaoSefaz?.status_emissao_sefaz === 'REJEITADA_HOMOLOGACAO' ||
            emissaoSefaz?.status_emissao_sefaz === 'REJEITADA_PRODUCAO'
              ? emissaoSefaz?.nfe?.xmotivo || 'NF-e rejeitada. Corrija os dados e reenvie.'
              : 'Revise os dados da NF-e antes de emitir. Use «Ver DANFE» para a prévia de conferência.'
          }
          variant="info"
          raw
        />
      ) : null}

      {autorizadaHomolog ? (
        <OperationalMessage
          title="NF-e autorizada em homologação"
          message={AVISO_HOMOLOG_SEM_VALOR_FISCAL}
          variant="success"
          raw
        />
      ) : null}

      {autorizadaProducao ? (
        <OperationalMessage
          title="NF-e autorizada em produção"
          message="Documento com validade fiscal. Cancelamento SEFAZ será disponibilizado em fase futura."
          variant="success"
          raw
        />
      ) : null}

      {autorizada && emissaoSefaz?.nfe?.protocolo ? (
        <div className="text-xs space-y-0.5 text-muted-foreground">
          <p>Protocolo: {emissaoSefaz.nfe.protocolo}</p>
          {emissaoSefaz.chave_acesso ? (
            <p className="font-mono break-all">Chave: {emissaoSefaz.chave_acesso}</p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm"
          disabled={danfeLoading}
          onClick={() => void abrirDanfe()}
        >
          {danfeLoading ? <Loader2 className="h-3 w-3 animate-spin inline mr-1" /> : null}
          {cancelada
            ? 'DANFE cancelado'
            : autorizadaHomolog
              ? 'DANFE (homologação)'
              : autorizadaProducao
                ? 'DANFE autorizado'
                : ACTION_LABELS.verDanfe}
        </button>

        {(autorizada || (cancelada && documentoAutorizadoLocal)) && documentoAutorizadoLocal ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={() => void baixarXmlAutorizado()}
          >
            {autorizadaProducao ? 'XML autorizado (produção)' : cancelada ? 'XML autorizado' : ACTION_LABELS.baixarXml}
          </button>
        ) : null}

        {(autorizadaProducao || cancelada) && emissaoSefaz?.chave_acesso ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={() => {
              void navigator.clipboard.writeText(emissaoSefaz.chave_acesso!).then(() => {
                toast.success('Chave de acesso copiada.');
              });
            }}
          >
            <Copy className="h-3 w-3 mr-1 inline" />
            Copiar chave
          </button>
        ) : null}

        {podeTentarEmitirHomolog && !autorizada && !cancelada ? (
          <button
            type="button"
            className="erp-btn-primary erp-btn-sm"
            disabled={emissaoLoading || !podeEmitirHomolog}
            onClick={onEmitir}
          >
            {emissaoLoading ? <Loader2 className="h-3 w-3 animate-spin inline mr-1" /> : null}
            {emissaoLoading ? 'Transmitindo…' : labelEmitir}
          </button>
        ) : null}
      </div>

      {children}

      <AdvancedSupportSection
        warningText="Informações para suporte técnico e diagnóstico. Não são necessárias para a operação diária."
      >
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={async () => {
              onPreviewError(null);
              try {
                onXmlPreview(await nfeSaidasService.previewXml(nfeId));
                onXmlModalOpen(true);
              } catch (err) {
                onPreviewError(apiErrorMessage(err));
              }
            }}
          >
            {TECHNICAL_DOWNLOAD_LABELS.previewXml}
          </button>
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={async () => {
              onPreviewError(null);
              try {
                onXmlPreview(await nfeSaidasService.previewXmlOficial(nfeId));
                onXmlModalOpen(true);
              } catch (err) {
                onPreviewError(apiErrorMessage(err));
              }
            }}
          >
            {TECHNICAL_DOWNLOAD_LABELS.xmlOficial}
          </button>
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            onClick={async () => {
              onPreviewError(null);
              try {
                onXmlPreview(await nfeSaidasService.previewXmlPreliminar(nfeId));
                onXmlModalOpen(true);
              } catch (err) {
                onPreviewError(apiErrorMessage(err));
              }
            }}
          >
            {TECHNICAL_DOWNLOAD_LABELS.xmlPreliminar}
          </button>
          {emissaoSefaz?.tem_xml_nfe_gerado || emissaoSefaz?.tem_xml_assinado ? (
            <a
              className="erp-btn-outline erp-btn-sm"
              href={nfeSaidasService.downloadXmlNfeUrl(nfeId)}
              target="_blank"
              rel="noreferrer"
            >
              Baixar XML NF-e (técnico)
            </a>
          ) : null}
          {emissaoSefaz?.tem_xml_assinado ? (
            <a
              className="erp-btn-outline erp-btn-sm"
              href={nfeSaidasService.downloadXmlAssinadoUrl(nfeId)}
              target="_blank"
              rel="noreferrer"
            >
              {TECHNICAL_DOWNLOAD_LABELS.xmlAssinado}
            </a>
          ) : null}
          {emissaoSefaz?.tem_xml_envio_lote ? (
            <a
              className="erp-btn-outline erp-btn-sm"
              href={nfeSaidasService.downloadXmlLoteEnviadoUrl(nfeId)}
              target="_blank"
              rel="noreferrer"
            >
              {TECHNICAL_DOWNLOAD_LABELS.xmlLote}
            </a>
          ) : null}
          {emissaoSefaz?.tem_xml_retorno ? (
            <a
              className="erp-btn-outline erp-btn-sm"
              href={nfeSaidasService.downloadXmlRetornoSefazUrl(nfeId)}
              target="_blank"
              rel="noreferrer"
            >
              {TECHNICAL_DOWNLOAD_LABELS.xmlRetorno}
            </a>
          ) : null}
          {!autorizada ? (
            <button
              type="button"
              className="erp-btn-outline erp-btn-sm"
              disabled={validarXmlLoading}
              onClick={onValidarXmlLocal}
            >
              {validarXmlLoading ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
                  Validando…
                </>
              ) : (
                TECHNICAL_DOWNLOAD_LABELS.validarXmlLocal
              )}
            </button>
          ) : null}
        </div>

        {validacaoXsdErros.length ? (
          <div className="rounded border border-destructive/30 p-2 space-y-1 max-h-32 overflow-y-auto">
            <p className="font-medium text-destructive">Erros de schema (XSD)</p>
            <ul className="list-disc pl-4 space-y-0.5">
              {validacaoXsdErros.map((e, i) => (
                <li key={`xsd-adv-${i}`}>
                  L{String(e.linha ?? '?')}: {formatNfeXsdErro(e)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {danfeMeta?.rendererOficial || danfeMeta?.rendererLabel || danfeMeta?.renderer ? (
          <div className="space-y-0.5 text-muted-foreground">
            <p>Renderer: {danfeMeta.rendererLabel || danfeMeta.rendererOficial || danfeMeta.renderer}</p>
            {danfeMeta.origem ? <p>Origem DANFE: {danfeMeta.origem}</p> : null}
          </div>
        ) : null}

        {emissaoSefaz?.status_emissao_sefaz ? (
          <p className="font-mono text-[11px] text-muted-foreground">
            status_emissao_sefaz: {emissaoSefaz.status_emissao_sefaz}
            {emissaoSefaz.nfe?.cstat ? ` · cStat ${emissaoSefaz.nfe.cstat}` : ''}
          </p>
        ) : null}
      </AdvancedSupportSection>
    </div>
  );
}
