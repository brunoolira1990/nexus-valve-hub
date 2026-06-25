import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { clientesService } from '@/services/api/clientes';
import { transportadorasService } from '@/services/api/transportadoras';
import { apiErrorMessage } from '@/services/api/config';
import type { Cliente, ContatoCliente, EnderecoEntregaCliente, Transportadora } from '@/types';
import type { EnderecoFiscalResumo } from '@/lib/enderecoFiscal';
import { ClienteForm, clientToFormValues, type ClienteFormInput } from './ClienteForm';

const ClienteFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [defaults, setDefaults] = useState<ClienteFormInput>(() => clientToFormValues({}));
  const [transportadoras, setTransportadoras] = useState<Transportadora[]>([]);
  const [enderecoFiscalInicial, setEnderecoFiscalInicial] = useState<EnderecoFiscalResumo | null>(null);
  const [enderecosEntregaInicial, setEnderecosEntregaInicial] = useState<EnderecoEntregaCliente[]>([]);
  const [contatosIniciais, setContatosIniciais] = useState<ContatoCliente[]>([]);

  useEffect(() => {
    transportadorasService.getAll().then(setTransportadoras).catch(() => setTransportadoras([]));
  }, []);

  useEffect(() => {
    if (!isEdit) {
      setDefaults(clientToFormValues({}));
      setEnderecoFiscalInicial(null);
      setEnderecosEntregaInicial([]);
      setContatosIniciais([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const c = await clientesService.getById(Number(id));
        if (!cancelled) {
          setDefaults(clientToFormValues(c));
          setEnderecoFiscalInicial(c.endereco_fiscal ?? null);
          setEnderecosEntregaInicial(c.enderecos_entrega ?? []);
          setContatosIniciais(c.contatos ?? []);
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

  const handleSubmit = async (payload: Omit<Cliente, 'id'>) => {
    setSaving(true);
    setError(null);
    try {
      if (isEdit) await clientesService.update(Number(id), payload);
      else await clientesService.create(payload);
      navigate('/clientes');
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader title={isEdit ? 'Editar cliente' : 'Novo cliente'} />
      {error && !loading && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-muted-foreground">Carregando…</p>
      ) : (
        <ClienteForm
          key={formKey}
          defaultValues={defaults}
          transportadoras={transportadoras}
          enderecosEntregaInicial={enderecosEntregaInicial}
          contatosIniciais={contatosIniciais}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/clientes')}
          saving={saving}
          enderecoFiscalInicial={enderecoFiscalInicial}
        />
      )}
    </div>
  );
};

export default ClienteFormPage;
