import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Save, Trash2 } from 'lucide-react';
import { Badge } from '@/components/nexus';
import { Chatter } from '@/components/layout/Chatter';
import { FormShell } from '@/components/layout/FormShell';
import { clientesService } from '@/services/api/clientes';
import { apiErrorMessage } from '@/services/api/config';
import {
  MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM,
  encontrarClienteIdPorCnpjExato,
  parseClienteSaveError,
} from '@/lib/clienteCadastroErros';
import type { Cliente, ContatoCliente, EnderecoEntregaCliente, Transportadora } from '@/types';
import type { EnderecoFiscalResumo } from '@/lib/enderecoFiscal';
import {
  ClienteForm,
  clientToFormValues,
  type ClienteFormHandle,
  type ClienteFormInput,
} from './ClienteForm';
import { transportadorasService } from '@/services/api/transportadoras';

const ClienteFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorHint, setErrorHint] = useState<string | null>(null);
  const [serverCnpjError, setServerCnpjError] = useState<string | null>(null);
  const [existingClientId, setExistingClientId] = useState<number | null>(null);
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
      setErrorHint(null);
      setServerCnpjError(null);
      setExistingClientId(null);
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
    setErrorHint(null);
    setServerCnpjError(null);
    setExistingClientId(null);
    try {
      if (isEdit) {
        await clientesService.update(Number(id), payload);
        navigate('/clientes');
      } else {
        // Cria já abre o registro novo: é a única forma de o Chatter ter entityId no primeiro salvamento.
        const criado = await clientesService.create(payload);
        navigate(`/clientes/${criado.id}/edit`, { replace: true });
      }
    } catch (e) {
      const parsed = parseClienteSaveError(e);
      // Mensagem principal do save (ex.: CNPJ duplicado) — a busca auxiliar nunca a substitui.
      setError(parsed.message);
      setServerCnpjError(parsed.cnpjError);
      if (parsed.isCnpjDuplicate && payload.cnpj) {
        try {
          const existingId = await encontrarClienteIdPorCnpjExato(payload.cnpj);
          setExistingClientId(existingId);
          if (existingId == null) {
            setErrorHint(MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM);
          }
        } catch {
          // Rede/401/403/erro inesperado na busca: mantém o banner de duplicidade, sem link.
          setExistingClientId(null);
          setErrorHint(null);
        }
      }
    } finally {
      setSaving(false);
    }
  };

  const clienteId = isEdit ? Number(id) : null;
  const formRef = useRef<ClienteFormHandle>(null);

  const titulo = defaults.razao_social.trim()
    ? [defaults.razao_social.trim(), defaults.cnpj.trim()].filter(Boolean).join(' — ')
    : isEdit
      ? 'Editar cliente'
      : 'Novo cliente';

  return (
    <FormShell
      titulo={titulo}
      meta={
        <Badge variant={defaults.bloqueado ? 'danger' : 'success'}>
          {defaults.bloqueado ? 'Bloqueado' : 'Ativo'}
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
          onClick: () => navigate('/clientes'),
        },
      ]}
      onVoltar={() => navigate('/clientes')}
      rail={<Chatter entityType="cliente" entityId={clienteId} />}
    >
      {error && !loading && (
        <div
          className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
          data-testid="cliente-form-save-error"
        >
          <p data-testid="cliente-form-save-error-main">{error}</p>
          {errorHint ? (
            <p className="mt-1 opacity-90" data-testid="cliente-form-save-error-hint">
              {errorHint}
            </p>
          ) : null}
          {existingClientId != null ? (
            <p className="mt-2">
              <Link
                to={`/clientes/${existingClientId}/edit`}
                className="underline font-medium text-destructive hover:opacity-90"
                data-testid="cliente-form-abrir-existente"
              >
                Abrir cliente existente
              </Link>
            </p>
          ) : null}
        </div>
      )}
      {loading ? (
        <p className="text-muted-foreground">Carregando…</p>
      ) : (
        <ClienteForm
          ref={formRef}
          key={formKey}
          defaultValues={defaults}
          transportadoras={transportadoras}
          enderecosEntregaInicial={enderecosEntregaInicial}
          contatosIniciais={contatosIniciais}
          onSubmit={handleSubmit}
          enderecoFiscalInicial={enderecoFiscalInicial}
          serverCnpjError={serverCnpjError}
        />
      )}
    </FormShell>
  );
};

export default ClienteFormPage;
