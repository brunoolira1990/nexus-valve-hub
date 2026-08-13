import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { clientesService } from '@/services/api/clientes';
import { apiErrorMessage } from '@/services/api/config';
import {
  MSG_CNPJ_DUPLICADO_ORIENTACAO_LISTAGEM,
  encontrarClienteIdPorCnpjExato,
  parseClienteSaveError,
} from '@/lib/clienteCadastroErros';
import type { Cliente, ContatoCliente, EnderecoEntregaCliente, Transportadora } from '@/types';
import type { EnderecoFiscalResumo } from '@/lib/enderecoFiscal';
import { ClienteForm, clientToFormValues, type ClienteFormInput } from './ClienteForm';
import { transportadorasService } from '@/services/api/transportadoras';
import { auditoriaService } from '@/services/api/auditoria';

const ClienteFormPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [podeVerHistorico, setPodeVerHistorico] = useState(false);
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
      setPodeVerHistorico(false);
      return;
    }
    let cancelled = false;
    auditoriaService
      .capacidade()
      .then((c) => {
        if (!cancelled) setPodeVerHistorico(Boolean(c.pode_visualizar));
      })
      .catch(() => {
        if (!cancelled) setPodeVerHistorico(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isEdit]);

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
      if (isEdit) await clientesService.update(Number(id), payload);
      else await clientesService.create(payload);
      navigate('/clientes');
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

  return (
    <div>
      <PageHeader
        title={isEdit ? 'Editar cliente' : 'Novo cliente'}
        breadcrumbs={[
          { label: 'Cadastros', path: '/clientes' },
          { label: 'Clientes', path: '/clientes' },
          { label: isEdit ? 'Editar' : 'Novo' },
        ]}
      />
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
          key={formKey}
          defaultValues={defaults}
          transportadoras={transportadoras}
          enderecosEntregaInicial={enderecosEntregaInicial}
          contatosIniciais={contatosIniciais}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/clientes')}
          saving={saving}
          enderecoFiscalInicial={enderecoFiscalInicial}
          serverCnpjError={serverCnpjError}
          clienteId={isEdit ? Number(id) : null}
          podeVerHistorico={podeVerHistorico}
        />
      )}
    </div>
  );
};

export default ClienteFormPage;
