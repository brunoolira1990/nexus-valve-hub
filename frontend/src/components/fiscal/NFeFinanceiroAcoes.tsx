import { useNavigate } from 'react-router-dom';
import { Wallet } from 'lucide-react';
import { isAutorizadaProducao } from '@/lib/nfeSaidaAcoesMatriz';
import { isAutorizadaHomologacao } from '@/lib/nfeSaidaUi';

type FinanceiroFlags = {
  financeiro_gerado?: boolean;
  pode_gerar_contas_receber?: boolean;
  motivo_bloqueio_financeiro?: string;
  contas_receber_vinculadas?: Array<{ id: number; numero: string }>;
  nfe_cancelada_com_financeiro?: boolean;
};

type Props = {
  nfeId: number;
  status?: string;
  statusEmissaoSefaz?: string;
  resumoEmissaoSefaz?: { status_emissao_sefaz?: string; nfe?: { cstat?: string } } | null;
  financeiro?: FinanceiroFlags | null;
  onGerar: () => void;
  className?: string;
};

export function NFeFinanceiroAcoes({
  nfeId,
  status,
  statusEmissaoSefaz,
  resumoEmissaoSefaz,
  financeiro,
  onGerar,
  className = '',
}: Props) {
  const navigate = useNavigate();
  const autorizadaHomolog = isAutorizadaHomologacao({
    status: status ?? '',
    status_emissao_sefaz: statusEmissaoSefaz,
    resumo_emissao_sefaz: resumoEmissaoSefaz ?? undefined,
  });
  const autorizadaProducao = isAutorizadaProducao(
    {
      status: status ?? '',
      status_emissao_sefaz: statusEmissaoSefaz,
      resumo_emissao_sefaz: resumoEmissaoSefaz ?? undefined,
    },
    resumoEmissaoSefaz ?? undefined,
  );
  const autorizada = autorizadaHomolog || autorizadaProducao;

  const flags = financeiro ?? {};
  const vinculados = flags.contas_receber_vinculadas ?? [];
  const primeiroTituloId = vinculados[0]?.id;

  const verContas = () => {
    if (primeiroTituloId) {
      navigate(`/financeiro/contas-receber?titulo=${primeiroTituloId}`);
      return;
    }
    navigate('/financeiro/contas-receber');
  };

  if (flags.financeiro_gerado) {
    return (
      <div className={`space-y-2 ${className}`}>
        {flags.nfe_cancelada_com_financeiro ? (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            Esta NF-e possui contas a receber vinculadas. A NF-e de origem foi cancelada — revise os títulos
            financeiros.
          </p>
        ) : null}
        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={verContas}>
          <Wallet className="h-3 w-3 mr-1" />
          Ver contas a receber
        </button>
        <p className="text-xs text-muted-foreground">
          {flags.motivo_bloqueio_financeiro || 'Contas a receber já foram geradas para esta NF-e.'}
        </p>
      </div>
    );
  }

  if (autorizadaHomolog) {
    return (
      <div className={className}>
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm opacity-50 cursor-not-allowed"
          disabled
          title="Financeiro indisponível para NF-e de homologação."
        >
          <Wallet className="h-3 w-3 mr-1" />
          Gerar contas a receber
        </button>
        <p className="text-xs text-muted-foreground mt-1">
          {flags.motivo_bloqueio_financeiro || 'Financeiro indisponível para NF-e de homologação.'}
        </p>
      </div>
    );
  }

  if (flags.pode_gerar_contas_receber) {
    return (
      <div className={className}>
        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={onGerar}>
          <Wallet className="h-3 w-3 mr-1" />
          Gerar contas a receber
        </button>
      </div>
    );
  }

  if (!autorizada) {
    return (
      <div className={className}>
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm opacity-50 cursor-not-allowed"
          disabled
          title="Disponível após autorização da NF-e."
        >
          <Wallet className="h-3 w-3 mr-1" />
          Gerar contas a receber
        </button>
        <p className="text-xs text-muted-foreground mt-1">
          {flags.motivo_bloqueio_financeiro || 'Disponível após autorização da NF-e.'}
        </p>
      </div>
    );
  }

  if (flags.motivo_bloqueio_financeiro) {
    return (
      <p className={`text-xs text-muted-foreground ${className}`}>{flags.motivo_bloqueio_financeiro}</p>
    );
  }

  return null;
}
