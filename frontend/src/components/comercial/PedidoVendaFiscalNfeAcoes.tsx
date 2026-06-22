import { useState } from 'react';
import { Download, ExternalLink, Eye, FileCode, Scale } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { downloadBlobFile, openBlobInNewTab } from '@/lib/downloadBlobFile';
import { nfeSaidasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { isNfeCanceladaOperacional, nfeTemDanfeHomologacao } from '@/lib/pedidoVendaModalUi';

type Props = {
  nfeSaidaId: number;
  nfeStatusEmissaoSefaz?: string;
  nfeSaidaStatus?: string;
};

export function PedidoVendaFiscalNfeAcoes({
  nfeSaidaId,
  nfeStatusEmissaoSefaz,
  nfeSaidaStatus,
}: Props) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<string | null>(null);

  const homolog = nfeTemDanfeHomologacao({
    nfe_status_emissao_sefaz: nfeStatusEmissaoSefaz,
    nfe_saida_status: nfeSaidaStatus,
  });
  const cancelada = isNfeCanceladaOperacional({ nfe_saida_status: nfeSaidaStatus });
  const autorizada =
    !cancelada &&
    (nfeStatusEmissaoSefaz === 'AUTORIZADA_PRODUCAO' ||
      nfeStatusEmissaoSefaz === 'AUTORIZADA_HOMOLOGACAO' ||
      nfeSaidaStatus === 'AUTORIZADA_PRODUCAO' ||
      nfeSaidaStatus === 'AUTORIZADA_HOMOLOGACAO' ||
      homolog);

  const runBlob = async (key: string, fn: () => Promise<{ blob: Blob; filename: string }>) => {
    setLoading(key);
    try {
      const { blob, filename } = await fn();
      downloadBlobFile(blob, filename);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível baixar o arquivo.' }));
    } finally {
      setLoading(null);
    }
  };

  const visualizarDanfe = async () => {
    setLoading('view');
    try {
      if (autorizada || cancelada) {
        const { blob } = await nfeSaidasService.danfeAutorizadoBlob(nfeSaidaId);
        openBlobInNewTab(blob);
        return;
      }
      const { blob } = await nfeSaidasService.previewDanfeBlob(nfeSaidaId);
      openBlobInNewTab(blob);
    } catch (e) {
      alert(apiErrorMessage(e, { fallback: 'Não foi possível visualizar o DANFE.' }));
    } finally {
      setLoading(null);
    }
  };

  const btnOutline =
    'erp-btn-outline erp-btn-sm inline-flex items-center justify-center gap-1 shrink-0 text-foreground';
  const btnPrimary =
    'erp-btn-primary erp-btn-sm inline-flex items-center justify-center gap-1 shrink-0';

  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        className={btnPrimary}
        onClick={() => navigate(`/nfe-saida?nfe=${nfeSaidaId}`)}
      >
        <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
        <span>Abrir NF-e</span>
      </button>
      <button
        type="button"
        className={btnOutline}
        disabled={!!loading}
        onClick={() => void visualizarDanfe()}
      >
        <Eye className="h-3 w-3 shrink-0" aria-hidden />
        <span>Visualizar DANFE</span>
      </button>
      <button
        type="button"
        className={btnOutline}
        disabled={!!loading}
        onClick={() =>
          void runBlob('danfe', () =>
            autorizada || cancelada
              ? nfeSaidasService.danfeAutorizadoBlob(nfeSaidaId)
              : nfeSaidasService.previewDanfeBlob(nfeSaidaId).then(({ blob }) => ({
                  blob,
                  filename: `danfe-nfe-${nfeSaidaId}.pdf`,
                })),
          )
        }
      >
        <Download className="h-3 w-3 shrink-0" aria-hidden />
        <span>Baixar DANFE</span>
      </button>
      {(autorizada || cancelada) ? (
        <button
          type="button"
          className={btnOutline}
          disabled={!!loading}
          onClick={() => void runBlob('xml', () => nfeSaidasService.downloadXmlAutorizadoBlob(nfeSaidaId))}
        >
          <FileCode className="h-3 w-3 shrink-0" aria-hidden />
          <span>Baixar XML</span>
        </button>
      ) : (
        <a
          className={btnOutline}
          href={nfeSaidasService.downloadXmlNfeUrl(nfeSaidaId)}
          target="_blank"
          rel="noopener noreferrer"
        >
          <FileCode className="h-3 w-3 shrink-0" aria-hidden />
          <span>Baixar XML</span>
        </a>
      )}
      <button
        type="button"
        className={btnOutline}
        onClick={() => navigate(`/nfe-saida?nfe=${nfeSaidaId}`)}
      >
        <Scale className="h-3 w-3 shrink-0" aria-hidden />
        <span>Efeitos e histórico</span>
      </button>
    </div>
  );
}
