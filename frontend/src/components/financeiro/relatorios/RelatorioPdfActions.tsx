import { useState } from 'react';
import { FileDown, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { NexusButton } from '@/components/nexus';
import {
  gerarRelatorioFinanceiroPdf,
  type RelatorioPdfEndpoint,
} from '@/lib/relatorioPdfDownload';
import type { RelatorioFiltrosState } from '@/lib/relatorioFinanceiro';

type Props = {
  endpoint: RelatorioPdfEndpoint;
  filtros: RelatorioFiltrosState;
  className?: string;
};

export function RelatorioPdfActions({ endpoint, filtros, className }: Props) {
  const [loading, setLoading] = useState(false);

  const onGerarPdf = async () => {
    setLoading(true);
    try {
      await gerarRelatorioFinanceiroPdf(endpoint, filtros);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Erro ao gerar PDF.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={className ?? 'flex flex-wrap gap-2 mb-4'}>
      <NexusButton
        variant="outline"
        size="sm"
        disabled={loading}
        onClick={() => void onGerarPdf()}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 mr-1 animate-spin" />
        ) : (
          <FileDown className="h-4 w-4 mr-1" />
        )}
        Gerar PDF
      </NexusButton>
    </div>
  );
}
