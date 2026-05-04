import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { clientesService } from '@/services/api/clientes';
import { apiErrorMessage } from '@/services/api/config';
import type { Cliente } from '@/types';

const ClienteList = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<Cliente[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await clientesService.getAll());
    } catch (e) {
      console.error('Falha ao carregar clientes:', e);
      setItems([]);
      setError(
        apiErrorMessage(e, {
          fallback: 'Não foi possível carregar os clientes.',
          preferGeneric: true,
        }),
      );
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await clientesService.delete(id);
      load();
    }
  };

  const filtered = items.filter(
    (i) => i.razao_social.toLowerCase().includes(search.toLowerCase()) || i.cnpj.includes(search),
  );

  return (
    <div>
      <PageHeader
        title="Clientes"
        onAdd={() => navigate('/clientes/novo')}
        addLabel="Novo cliente"
        searchValue={search}
        onSearch={setSearch}
      />
      <div className="erp-card overflow-x-auto">
        {error ? (
          <div className="m-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : null}
        <table className="erp-table">
          <thead>
            <tr>
              <th>Razão Social</th>
              <th>CNPJ</th>
              <th>Telefone</th>
              <th>Contato</th>
              <th className="w-24">Ações</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id}>
                <td className="font-medium">{e.razao_social}</td>
                <td>{e.cnpj}</td>
                <td>{e.telefone}</td>
                <td>{e.contato_responsavel}</td>
                <td>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => navigate(`/clientes/${e.id}/edit`)}
                      className="erp-btn-ghost erp-btn-sm"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(e.id)}
                      className="erp-btn-ghost erp-btn-sm text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!loading && !error && filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  Nenhum cliente encontrado.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClienteList;
