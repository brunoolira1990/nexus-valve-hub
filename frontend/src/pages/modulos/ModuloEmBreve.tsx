import { useParams } from 'react-router-dom';
import { BIPreparationState } from '@/components/bi/BIPreparationState';
import { PageHeader } from '@/components/PageHeader';

const MODULO_INFO: Record<string, { titulo: string; descricao: string }> = {
  crm: {
    titulo: 'CRM',
    descricao: 'Gestão de relacionamento com clientes, pipeline comercial e força de vendas.',
  },
  'gestao-resultado': {
    titulo: 'Gestão de Resultado',
    descricao: 'Indicadores de margem, custo real e estratégia de preços para apoio à decisão.',
  },
  'folha-rh': {
    titulo: 'Folha / RH',
    descricao: 'Folha de pagamento, frequência, benefícios e gestão de pessoas.',
  },
  sped: {
    titulo: 'SPED',
    descricao: 'Geração de arquivos SPED (EFD ICMS/IPI e Contribuições) para envio ao fisco.',
  },
};

type ModuloEmBreveProps = {
  moduloKey?: string;
};

export default function ModuloEmBreve({ moduloKey }: ModuloEmBreveProps) {
  const params = useParams();
  const key = moduloKey ?? params.modulo ?? '';
  const info = MODULO_INFO[key] ?? { titulo: 'Módulo', descricao: 'Funcionalidade em desenvolvimento.' };

  return (
    <div className="space-y-6">
      <PageHeader title={info.titulo} description="Módulo em desenvolvimento — em breve." />
      <BIPreparationState
        title={`${info.titulo} em breve`}
        message={`${info.descricao} Este módulo será disponibilizado em uma próxima versão do Nexus ERP.`}
      />
    </div>
  );
}
