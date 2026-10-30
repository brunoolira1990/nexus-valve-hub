import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Pencil } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Chatter } from '@/components/layout/Chatter';
import { FormShell } from '@/components/layout/FormShell';
import { ProdutoWorkspace } from './ProdutoWorkspace';
import { produtosService } from '@/services/api/produtos';
import type { Produto } from '@/types';

export default function ProdutoDetalhe() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [produto, setProduto] = useState<Produto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    if (!/^[1-9]\d*$/.test(id || '') || !Number.isSafeInteger(Number(id))) {
      setError('Identificador de produto inválido.');
      setLoading(false);
      return;
    }
    setLoading(true);
    produtosService
      .getById(Number(id))
      .then((produtoData) => {
        if (active) setProduto(produtoData);
        setLoading(false);
      })
      .catch(() => {
        if (active) setError('Não foi possível carregar o produto.');
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, attempt]);

  if (loading) return <p role="status" className="p-4 text-sm text-muted-foreground">Carregando produto...</p>;

  if (error) {
    return (
      <div className="p-4 space-y-4">
        <PageHeader
          title="Produto não encontrado"
          description="Ocorreu um erro ao carregar os dados do produto."
          breadcrumbs={[
            { label: 'Cadastros', path: '/produtos' },
            { label: 'Produtos', path: '/produtos' },
            { label: 'Erro' },
          ]}
        />
        <div className="space-y-2" role="alert">
          <p className="text-destructive">{error}</p>
          <button className="erp-btn-outline" onClick={() => setAttempt((n) => n + 1)}>
            Tentar novamente
          </button>
          <Link to="/produtos" className="erp-btn-outline">
            Voltar para listagem
          </Link>
        </div>
      </div>
    );
  }

  if (!produto) {
    return (
      <div className="p-4 space-y-4">
        <PageHeader
          title="Produto não encontrado"
          description="O produto solicitado não existe."
          breadcrumbs={[
            { label: 'Cadastros', path: '/produtos' },
            { label: 'Produtos', path: '/produtos' },
            { label: 'Não encontrado' },
          ]}
        />
        <Link to="/produtos" className="erp-btn-outline">
          Voltar para listagem
        </Link>
      </div>
    );
  }

  return (
    <FormShell
      titulo={`${produto.codigo_completo} — ${produto.descricao}`}
      acoesPrincipais={[
        {
          label: 'Editar',
          icon: <Pencil className="h-4 w-4 mr-2" />,
          variant: 'primary',
          onClick: () => navigate(`/produtos/${id}/editar`),
        },
      ]}
      onVoltar={() => navigate('/produtos')}
      rail={<Chatter entityType="produto" entityId={produto.id} />}
    >
      <ProdutoWorkspace produto={produto} mode="view" />
    </FormShell>
  );
}