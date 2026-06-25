import { useState } from 'react';
import { Download, ExternalLink, Eye, FileCode, Scale } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { downloadBlobFile, openBlobInNewTab } from '@/lib/downloadBlobFile';
import { nfeSaidasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import { deveUsarDanfeAutorizadoLinha } from '@/lib/nfeSaidaAcoesMatriz';

type Props = {
  nfeSaidaId: number;
  nfeStatusEmissaoSefaz?: string;
  nfeSaidaStatus?: string;
  temXmlAutorizado?: boolean;
};

export function PedidoVendaFiscalNfeAcoes({
  nfeSaidaId,
  nfeStatusEmissaoSefaz,
  nfeSaidaStatus,
  temXmlAutorizado,
}: Props) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState<string | null>(null);

  const usarDanfeAutorizado = deveUsarDanfeAutorizadoLinha({
    status: nfeSaidaStatus,
    status_emissao_sefaz: nfeStatusEmissaoSefaz,
    resumo_emissao_sefaz: {
      status_emissao_sefaz: nfeStatusEmissaoSefaz,
      tem_xml_autorizado: temXmlAutorizado,
    },
  });
  const documentoAutorizadoLocal = usarDanfeAutorizado;

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
      if (usarDanfeAutorizado) {
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
            usarDanfeAutorizado
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
      {documentoAutorizadoLocal ? (
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
