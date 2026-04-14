import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { fornecedoresService } from '@/services/api/fornecedores';
import type { Fornecedor } from '@/types';

const FornecedorList = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<Fornecedor[]>([]);
  const [search, setSearch] = useState('');

  const load = async () => setItems(await fornecedoresService.getAll());
  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await fornecedoresService.delete(id);
      load();
    }
  };

  const filtered = items.filter(
    (i) =>
      i.razao_social.toLowerCase().includes(search.toLowerCase()) ||
      (i.cnpj && i.cnpj.includes(search)),
  );

  return (
    <div>
      <PageHeader
        title="Fornecedores"
        onAdd={() => navigate('/fornecedores/novo')}
        addLabel="Novo fornecedor"
        searchValue={search}
        onSearch={setSearch}
      />
      <div className="erp-card overflow-x-auto">
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
                      onClick={() => navigate(`/fornecedores/${e.id}/edit`)}
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
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FornecedorList;
