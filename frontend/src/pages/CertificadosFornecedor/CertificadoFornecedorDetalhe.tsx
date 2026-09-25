import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { CertificadoFornecedorWorkspace } from './CertificadoFornecedorWorkspace';

const CertificadoFornecedorDetalhe = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  return (
    <div className="space-y-4">
      <PageHeader
        title={isEdit ? 'Editar certificado de fornecedor' : 'Novo certificado de fornecedor'}
        description="Cadastro de certificado recebido de fornecedor, com itens, corridas adicionais e dados tecnicos."
      />
      <CertificadoFornecedorWorkspace
        certificadoId={id ? Number(id) : null}
        onSaved={() => navigate('/certificados-fornecedor')}
        onCancel={() => navigate('/certificados-fornecedor')}
      />
    </div>
  );
};

export default CertificadoFornecedorDetalhe;
