import { useState, useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Pencil, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Modal } from '@/components/Modal';
import { condicoesPagamentoService } from '@/services/api/condicoesPagamento';
import { apiErrorMessage } from '@/services/api/config';
import type { CondicaoPagamento } from '@/types';

const formSchema = z.object({
  descricao: z.string().min(1, 'Obrigatório'),
  dias_parcelas_raw: z.string(),
  ativo: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

function parseDiasParcelas(raw: string): number[] {
  const parts = raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const out: number[] = [];
  for (const p of parts) {
    const n = parseInt(p, 10);
    if (Number.isNaN(n) || n < 0) {
      throw new Error(`Valor inválido: "${p}". Use inteiros separados por vírgula (ex: 30, 60).`);
    }
    out.push(n);
  }
  return out;
}

const emptyForm: FormValues = {
  descricao: '',
  dias_parcelas_raw: '',
  ativo: true,
};

const CondicoesPagamento = () => {
  const [items, setItems] = useState<CondicaoPagamento[]>([]);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CondicaoPagamento | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: emptyForm,
  });

  const load = async () => setItems(await condicoesPagamentoService.getAll());
  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setEditing(null);
    reset(emptyForm);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (row: CondicaoPagamento) => {
    setEditing(row);
    reset({
      descricao: row.descricao,
      dias_parcelas_raw: (row.dias_parcelas || []).join(', '),
      ativo: row.ativo,
    });
    setFormError(null);
    setModalOpen(true);
  };

  const onSave = handleSubmit(async (values) => {
    setFormError(null);
    let dias: number[];
    try {
      dias = parseDiasParcelas(values.dias_parcelas_raw);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Dias inválidos');
      return;
    }
    try {
      if (editing) {
        await condicoesPagamentoService.update(editing.id, {
          descricao: values.descricao,
          dias_parcelas: dias,
          ativo: values.ativo,
        });
      } else {
        await condicoesPagamentoService.create({
          descricao: values.descricao,
          dias_parcelas: dias,
          ativo: values.ativo,
        });
      }
      setModalOpen(false);
      load();
    } catch (e) {
      setFormError(apiErrorMessage(e));
    }
  });

  const handleDelete = async (id: number) => {
    if (confirm('Excluir esta condição de pagamento?')) {
      try {
        await condicoesPagamentoService.delete(id);
        load();
      } catch (e) {
        alert(apiErrorMessage(e));
      }
    }
  };

  const filtered = items.filter((i) => i.descricao.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <PageHeader
        title="Condições de pagamento"
        onAdd={openNew}
        addLabel="Nova condição"
        searchValue={search}
        onSearch={setSearch}
      />
      <div className="erp-card overflow-x-auto">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Descrição</th>
              <th>Dias (parcelas)</th>
              <th>Ativo</th>
              <th className="w-24">Ações</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td className="font-medium">{row.descricao}</td>
                <td>{(row.dias_parcelas || []).join(', ') || '—'}</td>
                <td>{row.ativo ? 'Sim' : 'Não'}</td>
                <td>
                  <div className="flex gap-1">
                    <button type="button" onClick={() => openEdit(row)} className="erp-btn-ghost erp-btn-sm">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(row.id)}
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

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Editar condição' : 'Nova condição'}
        size="md"
      >
        {formError && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {formError}
          </div>
        )}
        <form onSubmit={onSave} className="space-y-4">
          <div>
            <label className="erp-label">Descrição</label>
            <input className="erp-input mt-1" {...register('descricao')} />
            {errors.descricao && <p className="text-sm text-destructive mt-1">{errors.descricao.message}</p>}
          </div>
          <div>
            <label className="erp-label">Dias por parcela (separados por vírgula)</label>
            <input className="erp-input mt-1" placeholder="30, 45, 60" {...register('dias_parcelas_raw')} />
            <p className="text-xs text-muted-foreground mt-1">Ex.: 30,45 para duas parcelas aos 30 e 45 dias.</p>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <Controller
              name="ativo"
              control={control}
              render={({ field }) => (
                <input type="checkbox" checked={field.value} onChange={(e) => field.onChange(e.target.checked)} />
              )}
            />
            Ativo
          </label>
          <div className="flex justify-end gap-2 pt-4 border-t border-border">
            <button type="button" onClick={() => setModalOpen(false)} className="erp-btn-outline">
              Cancelar
            </button>
            <button type="submit" className="erp-btn-primary">
              Salvar
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default CondicoesPagamento;
