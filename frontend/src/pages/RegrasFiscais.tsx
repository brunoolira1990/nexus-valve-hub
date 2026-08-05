import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { ChecklistFiscalMinimo } from '@/components/fiscal/ChecklistFiscalMinimo';
import { RegrasFiscaisEntradaTab } from '@/components/RegrasFiscaisEntradaTab';
import { RegrasFiscaisLegadoTab } from '@/components/RegrasFiscaisLegadoTab';
import { RegrasFiscaisSaidaTab } from '@/components/RegrasFiscaisSaidaTab';

const RegrasFiscais = () => {
  const [searchParams] = useSearchParams();
  const [aba, setAba] = useState<'saida' | 'entrada'>('saida');

  useEffect(() => {
    if (searchParams.get('aba') === 'entrada') setAba('entrada');
  }, [searchParams]);

  const entradaPrefill = useMemo(
    () => ({
      cfop: searchParams.get('cfop') || searchParams.get('cfop_origem') || undefined,
      cfop_origem: searchParams.get('cfop_origem') || searchParams.get('cfop') || undefined,
      ncm: searchParams.get('ncm') || undefined,
      uf_origem: searchParams.get('uf_origem') || undefined,
      uf_destino: searchParams.get('uf_destino') || undefined,
      tipo_operacao_fiscal: searchParams.get('tipo_operacao_fiscal') || undefined,
      movimenta_estoque:
        searchParams.get('movimenta_estoque') === '0'
          ? false
          : searchParams.get('movimenta_estoque') === '1'
            ? true
            : undefined,
    }),
    [searchParams],
  );

  return (
    <div>
      <PageHeader
        title="Regras Fiscais"
        description="Cadastre e valide regras fiscais mínimas para produção. Não altera emissão de NF-e — apenas configuração e prontidão."
      />
      <ChecklistFiscalMinimo />
      <div className="flex gap-2 mb-4 border-b border-border">
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            aba === 'saida' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'
          }`}
          onClick={() => setAba('saida')}
        >
          Saída / Propostas
        </button>
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            aba === 'entrada' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'
          }`}
          onClick={() => setAba('entrada')}
        >
          Classificação de entrada
        </button>
      </div>

      {aba === 'entrada' ? (
        <RegrasFiscaisEntradaTab
          autoOpenNew={searchParams.get('nova') === '1'}
          prefill={entradaPrefill}
        />
      ) : (
        <>
          <RegrasFiscaisSaidaTab />
          <RegrasFiscaisLegadoTab />
        </>
      )}
    </div>
  );
};

export default RegrasFiscais;
