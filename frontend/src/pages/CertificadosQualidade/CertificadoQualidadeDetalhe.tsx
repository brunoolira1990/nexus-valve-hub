import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { CertificadoQualidadeWorkspace } from './CertificadoQualidadeWorkspace';

const CertificadoQualidadeDetalhe = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  return (
    <div className="space-y-4">
      <PageHeader
        title={isEdit ? 'Editar certificado de qualidade' : 'Novo certificado de qualidade'}
        description="Cadastro de certificado de qualidade do cliente, com itens, componentes e rastreabilidade."
      />
      <CertificadoQualidadeWorkspace
        certificadoId={id ? Number(id) : null}
        onSaved={() => navigate('/certificados')}
        onCancel={() => navigate('/certificados')}
      />
    </div>
  );
};

export default CertificadoQualidadeDetalhe;
