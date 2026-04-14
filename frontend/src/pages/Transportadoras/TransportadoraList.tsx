import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { transportadorasService } from '@/services/api/transportadoras';
import type { Transportadora } from '@/types';

const TransportadoraList = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<Transportadora[]>([]);
  const [search, setSearch] = useState('');

  const load = async () => setItems(await transportadorasService.getAll());
  useEffect(() => {
    load();
  }, []);

  const handleDelete = async (id: number) => {
    if (confirm('Excluir?')) {
      await transportadorasService.delete(id);
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
        title="Transportadoras"
        onAdd={() => navigate('/transportadoras/novo')}
        addLabel="Nova transportadora"
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
              <th>Placa</th>
              <th className="w-24">Ações</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id}>
                <td className="font-medium">{e.razao_social}</td>
                <td>{e.cnpj}</td>
                <td>{e.telefone}</td>
                <td>{e.placa_padrao}</td>
                <td>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => navigate(`/transportadoras/${e.id}/edit`)}
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

export default TransportadoraList;
