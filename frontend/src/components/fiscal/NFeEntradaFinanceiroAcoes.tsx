import { useNavigate } from 'react-router-dom';
import { Wallet } from 'lucide-react';
import { formatarAvisoPendenciasOperacionaisNfeEntrada } from '@/lib/conferenciaNfeLabels';

type FinanceiroFlags = {
  financeiro_gerado?: boolean;
  pode_gerar_contas_pagar?: boolean;
  motivo_bloqueio_financeiro?: string;
  possui_pendencias_operacionais?: boolean;
  aviso_pendencias_operacionais?: string;
  contas_pagar_vinculadas?: Array<{ id: number; numero: string }>;
  nfe_entrada_cancelada_com_financeiro?: boolean;
};

type Props = {
  nfeEntradaId: number;
  conferenciaStatus?: string;
  financeiro?: FinanceiroFlags | null;
  onGerar: () => void;
  className?: string;
};

export function NFeEntradaFinanceiroAcoes({
  nfeEntradaId,
  conferenciaStatus,
  financeiro,
  onGerar,
  className = '',
}: Props) {
  const navigate = useNavigate();
  const flags = financeiro ?? {};
  const vinculados = flags.contas_pagar_vinculadas ?? [];
  const primeiroTituloId = vinculados[0]?.id;
  const cancelada = conferenciaStatus === 'CANCELADA';

  const verContas = () => {
    if (primeiroTituloId) {
      navigate(`/financeiro/contas-pagar?titulo=${primeiroTituloId}`);
      return;
    }
    navigate('/financeiro/contas-pagar');
  };

  if (flags.financeiro_gerado) {
    return (
      <div className={`space-y-2 ${className}`}>
        {flags.nfe_entrada_cancelada_com_financeiro ? (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            Esta NF-e Entrada possui contas a pagar vinculadas. A NF-e de origem foi cancelada — revise os títulos
            financeiros.
          </p>
        ) : null}
        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={verContas}>
          <Wallet className="h-3 w-3 mr-1" />
          Ver contas a pagar
        </button>
      </div>
    );
  }

  if (flags.pode_gerar_contas_pagar) {
    return (
      <div className={`space-y-2 ${className}`}>
        {flags.possui_pendencias_operacionais ? (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            {formatarAvisoPendenciasOperacionaisNfeEntrada(flags.aviso_pendencias_operacionais)}
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            Gere o financeiro a partir das duplicatas da NF-e Entrada. A finalização da conferência e a aplicação de estoque não serão
            alteradas.
          </p>
        )}
        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={onGerar}>
          <Wallet className="h-3 w-3 mr-1" />
          Gerar contas a pagar
        </button>
      </div>
    );
  }

  if (cancelada) {
    return (
      <p className={`text-xs text-muted-foreground ${className}`}>
        {flags.motivo_bloqueio_financeiro || 'Esta NF-e Entrada está cancelada e não pode gerar contas a pagar.'}
      </p>
    );
  }

  return (
    <div className={className}>
      <button
        type="button"
        className="erp-btn-outline erp-btn-sm opacity-50 cursor-not-allowed"
        disabled
        title={flags.motivo_bloqueio_financeiro || 'Não disponível para gerar financeiro.'}
      >
        <Wallet className="h-3 w-3 mr-1" />
        Gerar contas a pagar
      </button>
      {flags.motivo_bloqueio_financeiro ? (
        <p className="text-xs text-muted-foreground mt-1">{flags.motivo_bloqueio_financeiro}</p>
      ) : null}
    </div>
  );
}
