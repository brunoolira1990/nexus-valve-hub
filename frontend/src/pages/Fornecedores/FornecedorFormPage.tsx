import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { fornecedoresService } from '@/services/api/fornecedores';
import { condicoesPagamentoService } from '@/services/api/condicoesPagamento';
import { transportadorasService } from '@/services/api/transportadoras';
import { apiErrorMessage } from '@/services/api/config';
import type { CondicaoPagamento, Fornecedor, Transportadora } from '@/types';
import { FornecedorForm, fornecedorToFormValues, type FornecedorFormInput } from './FornecedorForm';

const FornecedorFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [defaults, setDefaults] = useState<FornecedorFormInput>(() => fornecedorToFormValues({}));
  const [condicoes, setCondicoes] = useState<CondicaoPagamento[]>([]);
  const [transportadoras, setTransportadoras] = useState<Transportadora[]>([]);

  useEffect(() => {
    condicoesPagamentoService.getAll().then(setCondicoes).catch(() => setCondicoes([]));
    transportadorasService.getAll().then(setTransportadoras).catch(() => setTransportadoras([]));
  }, []);

  useEffect(() => {
    if (!isEdit) {
      setDefaults(fornecedorToFormValues({}));
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const f = await fornecedoresService.getById(Number(id));
        if (!cancelled) {
          setDefaults(fornecedorToFormValues(f));
          setFormKey((k) => k + 1);
        }
      } catch (e) {
        if (!cancelled) setError(apiErrorMessage(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, isEdit]);

  const handleSubmit = async (payload: Omit<Fornecedor, 'id'>) => {
    setSaving(true);
    setError(null);
    try {
      if (isEdit) await fornecedoresService.update(Number(id), payload);
      else await fornecedoresService.create(payload);
      navigate('/fornecedores');
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title={isEdit ? 'Editar fornecedor' : 'Novo fornecedor'} />
      {error && !loading && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-muted-foreground">Carregando…</p>
      ) : (
        <FornecedorForm
          key={formKey}
          defaultValues={defaults}
          condicoes={condicoes}
          transportadoras={transportadoras}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/fornecedores')}
          saving={saving}
        />
      )}
    </div>
  );
};

export default FornecedorFormPage;
