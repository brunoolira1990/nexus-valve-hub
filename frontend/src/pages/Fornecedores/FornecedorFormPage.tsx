import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Save, Trash2 } from 'lucide-react';
import { Badge } from '@/components/nexus';
import { Chatter } from '@/components/layout/Chatter';
import { FormShell } from '@/components/layout/FormShell';
import { fornecedoresService } from '@/services/api/fornecedores';
import { transportadorasService } from '@/services/api/transportadoras';
import { apiErrorMessage } from '@/services/api/config';
import type { Fornecedor, Transportadora } from '@/types';
import {
  FornecedorForm,
  fornecedorToFormValues,
  type FornecedorFormHandle,
  type FornecedorFormInput,
} from './FornecedorForm';

const FornecedorFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [defaults, setDefaults] = useState<FornecedorFormInput>(() => fornecedorToFormValues({}));
  const [transportadoras, setTransportadoras] = useState<Transportadora[]>([]);

  useEffect(() => {
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
      if (isEdit) {
        await fornecedoresService.update(Number(id), payload);
        navigate('/fornecedores');
      } else {
        // Cria já abre o registro novo: é a única forma de o Chatter ter entityId no primeiro salvamento.
        const criado = await fornecedoresService.create(payload);
        navigate(`/fornecedores/${criado.id}/edit`, { replace: true });
      }
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const fornecedorId = isEdit ? Number(id) : null;
  const formRef = useRef<FornecedorFormHandle>(null);

  const titulo = defaults.razao_social.trim()
    ? [defaults.razao_social.trim(), defaults.cnpj.trim()].filter(Boolean).join(' — ')
    : isEdit
      ? 'Editar fornecedor'
      : 'Novo fornecedor';

  return (
    <FormShell
      titulo={titulo}
      meta={
        <Badge variant={defaults.ativo ? 'success' : 'neutral'}>
          {defaults.ativo ? 'Ativo' : 'Inativo'}
        </Badge>
      }
      acoesPrincipais={[
        {
          label: 'Salvar',
          icon: <Save className="h-4 w-4 mr-2" />,
          variant: 'primary',
          loading: saving,
          onClick: () => formRef.current?.salvar(),
        },
      ]}
      acoesSecundarias={[
        {
          label: 'Descartar',
          icon: <Trash2 className="h-4 w-4 mr-2" />,
          onClick: () => navigate('/fornecedores'),
        },
      ]}
      onVoltar={() => navigate('/fornecedores')}
      rail={<Chatter entityType="fornecedor" entityId={fornecedorId} />}
    >
      {error && !loading && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-muted-foreground">Carregando…</p>
      ) : (
        <FornecedorForm
          ref={formRef}
          key={formKey}
          defaultValues={defaults}
          transportadoras={transportadoras}
          onSubmit={handleSubmit}
        />
      )}
    </FormShell>
  );
};

export default FornecedorFormPage;
