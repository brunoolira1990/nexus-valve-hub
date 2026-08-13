import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { transportadorasService } from '@/services/api/transportadoras';
import { apiErrorMessage } from '@/services/api/config';
import type { Transportadora } from '@/types';
import { TransportadoraForm, transportadoraToFormValues, type TransportadoraFormInput } from './TransportadoraForm';

const TransportadoraFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [defaults, setDefaults] = useState<TransportadoraFormInput>(() => transportadoraToFormValues({}));

  useEffect(() => {
    if (!isEdit) {
      setDefaults(transportadoraToFormValues({}));
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const t = await transportadorasService.getById(Number(id));
        if (!cancelled) {
          setDefaults(transportadoraToFormValues(t));
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

  const handleSubmit = async (payload: Omit<Transportadora, 'id'>) => {
    setSaving(true);
    setError(null);
    try {
      if (isEdit) await transportadorasService.update(Number(id), payload);
      else await transportadorasService.create(payload);
      navigate('/transportadoras');
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={isEdit ? 'Editar transportadora' : 'Nova transportadora'}
        breadcrumbs={[
          { label: 'Cadastros', path: '/transportadoras' },
          { label: 'Transportadoras', path: '/transportadoras' },
          { label: isEdit ? 'Editar' : 'Nova' },
        ]}
      />
      {error && !loading && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-muted-foreground">Carregando…</p>
      ) : (
        <TransportadoraForm
          key={formKey}
          defaultValues={defaults}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/transportadoras')}
          saving={saving}
        />
      )}
    </div>
  );
};

export default TransportadoraFormPage;
