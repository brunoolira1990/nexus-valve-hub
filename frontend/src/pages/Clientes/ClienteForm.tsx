import type { ChangeEventHandler, FocusEvent, KeyboardEvent } from 'react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  CadastroButton,
  CadastroFormShell,
  CadastroSection,
  CadastroTabs,
  CheckboxField,
  InputField,
  SelectField,
  TextareaField,
} from '@/components/ui/cadastro';
import { ConsultaCnpjSugestoesPanel } from '@/components/cadastros/ConsultaCnpjSugestoesPanel';
import { ConsultaIeSefazControls } from '@/components/cadastros/ConsultaIeSefazControls';
import { useConsultaIeSefaz } from '@/hooks/useConsultaIeSefaz';
import { consultaCep, consultaCnpj } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import {
  aplicarConsultaCnpjCamposVazios,
  MAPEAMENTO_CNPJ_CLIENTE,
  mensagemSucessoConsultaCnpj,
  montarSugestoesCnpj,
  type CampoSugestaoCnpj,
} from '@/lib/consultaCnpjCadastro';
import {
  enderecoFiscalInconsistenteLocal,
  mensagemEnderecoFiscalInconsistente,
  mensagemEnderecoFiscalResumo,
  type EnderecoFiscalResumo,
} from '@/lib/enderecoFiscal';
import { isValidCnpj, normalizeCnpj } from '@/lib/cnpj';
import { digitsOnly, formatCep, formatCnpj, formatPhone } from '@/lib/masks';
import { parsePaymentCondition } from '@/lib/paymentTerms';
import {
  ClienteContatosAdicionaisEditor,
  contatosClienteParaApi,
  enderecosEntregaParaApi,
} from '@/components/clientes/ClienteContatosAdicionaisEditor';
import {
  contatosClienteTemErro,
  validarContatosCliente,
} from '@/lib/clienteContatosFiscais';
import { ClienteEnderecosEntregaEditor } from '@/components/clientes/ClienteEnderecosEntregaEditor';
import { HistoricoAlteracoesPanel } from '@/components/auditoria/HistoricoAlteracoesPanel';
import type { Cliente, ContatoCliente, EnderecoEntregaCliente, Transportadora } from '@/types';
import { REGIMES_CADASTRO, TIPOS_CONTA, UFS } from '@/types';

const emailOrEmpty = z.union([z.literal(''), z.string().email('E-mail inválido')]);

const schema = z.object({
  razao_social: z.string().min(1, 'Obrigatório'),
  nome_fantasia: z.string(),
  cnpj: z
    .string()
    .min(1, 'Obrigatório')
    .refine((v) => normalizeCnpj(v).length === 14, 'CNPJ deve ter 14 dígitos')
    .refine((v) => isValidCnpj(v), 'CNPJ inválido'),
  ddd: z.string(),
  ie: z.string(),
  ie_isento: z.boolean(),
  inscricao_municipal: z.string(),
  suframa: z.string(),
  cep: z.string(),
  logradouro: z.string(),
  numero: z.string(),
  complemento: z.string(),
  bairro: z.string(),
  cidade: z.string(),
  uf: z.string(),
  telefone: z.string(),
  telefone_alternativo: z.string(),
  celular: z.string(),
  email: emailOrEmpty,
  email_nf: emailOrEmpty,
  contato_responsavel: z.string(),
  banco: z.string(),
  agencia: z.string(),
  conta: z.string(),
  tipo_conta: z.string(),
  cnae: z.string(),
  regime_tributario: z.string(),
  integracao_texto: z.string(),
  limite_credito: z.coerce.number().min(0),
  condicao_pagamento_texto: z.string(),
  transportadora_padrao_id: z.string(),
  vendedor_padrao: z.string(),
  bloqueado: z.boolean(),
  ativo: z.boolean(),
  observacoes: z.string(),
  informacoes_complementares_nfe: z.string(),
});

export type ClienteFormInput = z.infer<typeof schema>;

const TAB_ITEMS_BASE = [
  { id: 'dados-gerais', label: 'Dados Gerais' },
  { id: 'endereco', label: 'Endereço' },
  { id: 'contatos', label: 'Contatos' },
  { id: 'nfe-danfe', label: 'NF-e / DANFE' },
  { id: 'fiscal-financeiro', label: 'Fiscal / Financeiro' },
  { id: 'observacoes', label: 'Observações' },
] as const;

const regimeOptions = [
  { value: '', label: 'Selecione…' },
  ...REGIMES_CADASTRO.map((r) => ({ value: r, label: r })),
];

const tipoContaOptions = [{ value: '', label: 'Selecione…' }, ...TIPOS_CONTA];

const ufOptions = UFS.map((u) => ({ value: u, label: u }));

function toApiPayload(
  values: ClienteFormInput,
  enderecosEntrega: EnderecoEntregaCliente[],
  contatos: ContatoCliente[],
): Omit<Cliente, 'id'> {
  return {
    razao_social: values.razao_social,
    nome_fantasia: values.nome_fantasia,
    cnpj: normalizeCnpj(values.cnpj),
    ie: values.ie_isento ? '' : values.ie,
    ie_isento: values.ie_isento,
    logradouro: values.logradouro,
    numero: values.numero,
    complemento: values.complemento,
    bairro: values.bairro,
    cidade: values.cidade,
    uf: values.uf,
    cep: digitsOnly(values.cep, 8),
    telefone: digitsOnly(values.telefone, 11),
    email: values.email,
    contato_responsavel: values.contato_responsavel,
    observacoes: values.observacoes,
    inscricao_municipal: values.inscricao_municipal,
    suframa: values.suframa,
    email_nf: values.email_nf,
    telefone_alternativo: digitsOnly(values.telefone_alternativo, 11),
    celular: digitsOnly(values.celular, 11),
    limite_credito: values.limite_credito,
    condicao_pagamento_texto: values.condicao_pagamento_texto.trim(),
    transportadora_padrao_id:
      values.transportadora_padrao_id === '' ? null : Number(values.transportadora_padrao_id),
    vendedor_padrao: values.vendedor_padrao,
    bloqueado: values.bloqueado,
    ativo: values.ativo,
    ddd: digitsOnly(values.ddd, 4),
    banco: values.banco,
    agencia: values.agencia,
    conta: values.conta,
    tipo_conta: values.tipo_conta,
    cnae: values.cnae,
    regime_tributario: values.regime_tributario,
    integracao_texto: values.integracao_texto,
    informacoes_complementares_nfe: values.informacoes_complementares_nfe,
    enderecos_entrega: enderecosEntregaParaApi(enderecosEntrega),
    contatos: contatosClienteParaApi(contatos),
  };
}

export function clientToFormValues(c: Partial<Cliente>): ClienteFormInput {
  return {
    razao_social: c.razao_social ?? '',
    nome_fantasia: c.nome_fantasia ?? '',
    cnpj: formatCnpj(c.cnpj ?? ''),
    ddd: digitsOnly(c.ddd ?? '', 4),
    ie: c.ie ?? '',
    ie_isento: c.ie_isento ?? (c.ie ?? '').trim().toUpperCase() === 'ISENTO',
    inscricao_municipal: c.inscricao_municipal ?? '',
    suframa: c.suframa ?? '',
    cep: formatCep(c.cep ?? ''),
    logradouro: c.logradouro ?? '',
    numero: c.numero ?? '',
    complemento: c.complemento ?? '',
    bairro: c.bairro ?? '',
    cidade: c.cidade ?? '',
    uf: c.uf ?? '',
    telefone: formatPhone(c.telefone ?? ''),
    telefone_alternativo: formatPhone(c.telefone_alternativo ?? ''),
    celular: formatPhone(c.celular ?? ''),
    email: c.email ?? '',
    email_nf: c.email_nf ?? '',
    limite_credito: c.limite_credito ?? 0,
    condicao_pagamento_texto: c.condicao_pagamento_texto ?? '',
    transportadora_padrao_id:
      c.transportadora_padrao_id != null ? String(c.transportadora_padrao_id) : '',
    bloqueado: c.bloqueado ?? false,
    ativo: c.ativo ?? true,
    vendedor_padrao: c.vendedor_padrao ?? '',
    observacoes: c.observacoes ?? '',
    contato_responsavel: c.contato_responsavel ?? '',
    banco: c.banco ?? '',
    agencia: c.agencia ?? '',
    conta: c.conta ?? '',
    tipo_conta: c.tipo_conta ?? '',
    cnae: c.cnae ?? '',
    regime_tributario: c.regime_tributario ?? '',
    integracao_texto: c.integracao_texto ?? '',
    informacoes_complementares_nfe: c.informacoes_complementares_nfe ?? '',
  };
}

type Props = {
  defaultValues: ClienteFormInput;
  transportadoras: Transportadora[];
  enderecosEntregaInicial?: EnderecoEntregaCliente[];
  contatosIniciais?: ContatoCliente[];
  onSubmit: (payload: Omit<Cliente, 'id'>) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
  enderecoFiscalInicial?: EnderecoFiscalResumo | null;
  /** Erro de validação do servidor no campo CNPJ (ex.: duplicidade). */
  serverCnpjError?: string | null;
  /** ID do cliente em edição — necessário para a aba Histórico. */
  clienteId?: number | null;
  /** Exibe aba Histórico somente com permissão de auditoria. */
  podeVerHistorico?: boolean;
};

function AlertaEnderecoFiscal({ mensagem }: { mensagem: string }) {
  if (!mensagem) return null;
  return (
    <div
      className="md:col-span-2 rounded-md border border-amber-500/35 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100"
      data-testid="alerta-endereco-fiscal-cliente"
    >
      {mensagem}
      <p className="text-xs mt-1 opacity-90">
        O cadastro pode ser salvo para uso comercial, mas a NF-e ficará bloqueada até a correção do endereço fiscal.
      </p>
    </div>
  );
}

export function ClienteForm({
  defaultValues,
  transportadoras,
  enderecosEntregaInicial = [],
  contatosIniciais = [],
  onSubmit,
  onCancel,
  saving,
  enderecoFiscalInicial,
  serverCnpjError = null,
  clienteId = null,
  podeVerHistorico = false,
}: Props) {
  const tabItems = podeVerHistorico && clienteId
    ? [...TAB_ITEMS_BASE, { id: 'historico', label: 'Histórico' }]
    : [...TAB_ITEMS_BASE];
  const [tab, setTab] = useState<string>(TAB_ITEMS_BASE[0].id);
  const [enderecosEntrega, setEnderecosEntrega] = useState<EnderecoEntregaCliente[]>(
    () => enderecosEntregaInicial,
  );
  const [contatos, setContatos] = useState<ContatoCliente[]>(() => contatosIniciais);
  const [contatosErros, setContatosErros] = useState<
    ReturnType<typeof validarContatosCliente>
  >([]);
  const [cnpjLookupLoading, setCnpjLookupLoading] = useState(false);
  const consultaIe = useConsultaIeSefaz();
  const [cnpjLookupMessage, setCnpjLookupMessage] = useState<string | null>(null);
  const [cnpjSugestoes, setCnpjSugestoes] = useState<CampoSugestaoCnpj<keyof ClienteFormInput>[]>([]);
  const [lastLookupCnpj, setLastLookupCnpj] = useState<string | null>(null);
  const [cepLookupLoading, setCepLookupLoading] = useState(false);
  const [cepLookupMessage, setCepLookupMessage] = useState<string | null>(null);
  const [lastLookupCep, setLastLookupCep] = useState<string | null>(null);
  const [enderecoFiscalAlerta, setEnderecoFiscalAlerta] = useState(
    () => mensagemEnderecoFiscalResumo(enderecoFiscalInicial) || '',
  );

  const {
    register,
    control,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    getValues,
    watch,
    formState: { errors },
  } = useForm<ClienteFormInput>({
    resolver: zodResolver(schema),
    defaultValues,
  });
  const aplicarIeNoFormulario = (valor: string) => {
    setValue('ie_isento', false, { shouldDirty: true });
    setValue('ie', valor, { shouldDirty: true, shouldValidate: true });
  };
  const ieIsento = watch('ie_isento');

  useEffect(() => {
    if (ieIsento) {
      setValue('ie', '', { shouldDirty: true, shouldValidate: true });
    }
  }, [ieIsento, setValue]);

  useEffect(() => {
    if (serverCnpjError) {
      setError('cnpj', { type: 'server', message: serverCnpjError });
      setTab('dados-gerais');
    }
  }, [serverCnpjError, setError]);

  const cnpjField = register('cnpj');
  const cepField = register('cep');
  const dddField = register('ddd');
  const telefoneField = register('telefone');
  const telefoneAlternativoField = register('telefone_alternativo');
  const celularField = register('celular');

  const setIfEmpty = (field: keyof ClienteFormInput, nextValue: string) => {
    const currentValue = getValues(field);
    if ((currentValue ?? '').toString().trim() !== '') return;
    if ((nextValue ?? '').toString().trim() === '') return;
    setValue(field, nextValue);
  };

  useEffect(() => {
    const cep = digitsOnly(defaultValues.cep, 8);
    if (cep.length !== 8) return;
    let cancelled = false;
    void consultaCep(cep)
      .then(({ data }) => {
        if (cancelled) return;
        if (
          enderecoFiscalInconsistenteLocal(defaultValues.cidade, defaultValues.uf, data)
        ) {
          setEnderecoFiscalAlerta(
            mensagemEnderecoFiscalInconsistente(
              defaultValues.cidade,
              defaultValues.cep,
              defaultValues.uf,
              data,
            ),
          );
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [defaultValues.cep, defaultValues.cidade, defaultValues.uf]);

  const runCepLookup = async (rawValue: string, force = false) => {
    const cep = digitsOnly(rawValue, 8);
    if (cep.length !== 8) return;
    if (cepLookupLoading) return;
    if (!force && lastLookupCep === cep) return;
    clearErrors('root');
    setCepLookupMessage(null);
    setCepLookupLoading(true);
    try {
      const { data } = await consultaCep(cep);
      if (force) {
        setValue('logradouro', data.logradouro || '');
        setValue('complemento', data.complemento || '');
        setValue('bairro', data.bairro || '');
      } else {
        setIfEmpty('logradouro', data.logradouro || '');
        setIfEmpty('complemento', data.complemento || '');
        setIfEmpty('bairro', data.bairro || '');
      }
      setValue('cidade', data.cidade || '');
      setValue('uf', data.uf || '');
      if (data.cep) setValue('cep', formatCep(data.cep));
      setLastLookupCep(cep);
      const inconsistente = enderecoFiscalInconsistenteLocal(data.cidade, data.uf, data);
      setEnderecoFiscalAlerta(
        inconsistente
          ? mensagemEnderecoFiscalInconsistente(data.cidade, data.cep, data.uf, data)
          : '',
      );
      setCepLookupMessage(
        inconsistente
          ? 'CEP consultado, mas há divergência entre cidade/UF informadas.'
          : 'Endereço encontrado pelo CEP.',
      );
    } catch (err) {
      const msg = apiErrorMessage(err);
      setCepLookupMessage(msg);
      setError('root', { message: msg });
    } finally {
      setCepLookupLoading(false);
    }
  };

  const onCepBlur = async (e: FocusEvent<HTMLInputElement>) => {
    cepField.onBlur(e);
    await runCepLookup(e.target.value);
  };

  const runCnpjLookup = async (rawValue: string, force = false) => {
    const cnpj = normalizeCnpj(rawValue);
    if (cnpj.length !== 14) {
      if (digitsOnly(rawValue, 14)) {
        setCnpjLookupMessage('CNPJ inválido. Informe 14 dígitos.');
      }
      return;
    }
    if (!isValidCnpj(cnpj)) {
      setCnpjSugestoes([]);
      setCnpjLookupMessage('CNPJ inválido. Verifique os dígitos verificadores.');
      return;
    }
    if (cnpjLookupLoading) return;
    if (!force && lastLookupCnpj === cnpj) return;

    clearErrors('root');
    setCnpjLookupMessage(null);
    setCnpjSugestoes([]);
    setCnpjLookupLoading(true);
    try {
      const { data } = await consultaCnpj(cnpj);
      const valoresAtuais = getValues();
      const updates = aplicarConsultaCnpjCamposVazios(valoresAtuais, data, MAPEAMENTO_CNPJ_CLIENTE);
      for (const [campo, valor] of Object.entries(updates) as [keyof ClienteFormInput, string][]) {
        setValue(campo, valor);
      }
      setCnpjSugestoes(montarSugestoesCnpj(valoresAtuais, data, MAPEAMENTO_CNPJ_CLIENTE));
      setEnderecoFiscalAlerta('');
      setLastLookupCnpj(cnpj);
      setCnpjLookupMessage(mensagemSucessoConsultaCnpj(data));
      await consultaIe.tryAutoConsultaIe(
        getValues('cnpj'),
        getValues('uf') || data.uf || '',
        getValues('ie'),
        aplicarIeNoFormulario,
      );
    } catch (err) {
      const msg = apiErrorMessage(err, {
        fallback: 'Não foi possível consultar o CNPJ agora. Você pode preencher os dados manualmente.',
      });
      setCnpjLookupMessage(msg);
      setError('root', { message: msg });
    } finally {
      setCnpjLookupLoading(false);
    }
  };

  const aplicarSugestaoCnpj = (campo: keyof ClienteFormInput, valor: string) => {
    setValue(campo, valor);
    setCnpjSugestoes((prev) => prev.filter((item) => item.campo !== campo));
  };

  const aplicarTodasSugestoesCnpj = () => {
    for (const item of cnpjSugestoes) {
      setValue(item.campo, item.sugerido);
    }
    setCnpjSugestoes([]);
  };

  const onCnpjBlur = async (e: FocusEvent<HTMLInputElement>) => {
    cnpjField.onBlur(e);
    await runCnpjLookup(e.target.value);
  };

  const onCnpjChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    const masked = formatCnpj(e.target.value);
    cnpjField.onChange({
      ...e,
      target: { ...e.target, value: masked, name: cnpjField.name },
    });
  };

  const onDddChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    const digits = digitsOnly(e.target.value, 4);
    dddField.onChange({
      ...e,
      target: { ...e.target, value: digits, name: dddField.name },
    });
  };

  const onCepChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    const masked = formatCep(e.target.value);
    cepField.onChange({
      ...e,
      target: { ...e.target, value: masked, name: cepField.name },
    });
  };

  const onTelefoneChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    const masked = formatPhone(e.target.value);
    telefoneField.onChange({
      ...e,
      target: { ...e.target, value: masked, name: telefoneField.name },
    });
  };

  const onTelefoneAlternativoChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    const masked = formatPhone(e.target.value);
    telefoneAlternativoField.onChange({
      ...e,
      target: { ...e.target, value: masked, name: telefoneAlternativoField.name },
    });
  };

  const onCelularChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    const masked = formatPhone(e.target.value);
    celularField.onChange({
      ...e,
      target: { ...e.target, value: masked, name: celularField.name },
    });
  };

  const onCnpjKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter' && e.key !== 'Tab') return;
    void runCnpjLookup(e.currentTarget.value);
  };

  const onCepKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter' && e.key !== 'Tab') return;
    void runCepLookup(e.currentTarget.value);
  };

  const transportadoraOptions = transportadoras.map((t) => ({ value: String(t.id), label: t.razao_social }));
  const condicaoPreview = (() => {
    try {
      return parsePaymentCondition(getValues('condicao_pagamento_texto'));
    } catch {
      return null;
    }
  })();

  const panel = (
    <CadastroSection
      title={tabItems.find((t) => t.id === tab)?.label ?? ''}
      description={
        tab === 'dados-gerais'
          ? 'Base cadastral e identificação principal do cliente.'
          : tab === 'endereco'
            ? 'Localização fiscal e logística para faturamento e entrega.'
            : tab === 'contatos'
              ? 'Canal oficial de relacionamento, cobrança e envio de documentos.'
              : tab === 'nfe-danfe'
                ? 'Textos recorrentes deste cliente que saem em Dados Adicionais da NF-e e da DANFE.'
                : tab === 'fiscal-financeiro'
                  ? 'Informações fiscais, bancárias e regras comerciais do cadastro.'
                  : 'Textos para a DANFE (saem na NF-e) e observações internas do ERP (não saem na NF-e).'
      }
    >
      {tab === 'dados-gerais' && (
        <>
          <InputField label="Razão Social *" operationalUpper {...register('razao_social')} error={errors.razao_social?.message} />
          <InputField label="Nome Fantasia" operationalUpper {...register('nome_fantasia')} />
          <div>
            <InputField
              label="CNPJ *"
              {...cnpjField}
              onChange={onCnpjChange}
              onBlur={onCnpjBlur}
              onKeyDown={onCnpjKeyDown}
              error={errors.cnpj?.message}
            />
            <div className="mt-1 text-xs text-muted-foreground">
              {cnpjLookupLoading
                ? 'Consultando CNPJ...'
                : cnpjLookupMessage ?? 'A consulta ocorre automaticamente ao sair do campo.'}
            </div>
          </div>
          <ConsultaCnpjSugestoesPanel
            sugestoes={cnpjSugestoes}
            onAplicarCampo={aplicarSugestaoCnpj}
            onAplicarTodas={aplicarTodasSugestoesCnpj}
          />
          <CheckboxField
            control={control}
            name="ie_isento"
            label="Isento de Inscrição Estadual"
          />
          {!ieIsento ? (
            <>
              <InputField label="Inscrição Estadual (IE)" operationalUpper {...register('ie')} />
              <ConsultaIeSefazControls
                consultaIe={consultaIe}
                getCnpj={() => getValues('cnpj')}
                getUf={() => getValues('uf')}
                getIeAtual={() => getValues('ie')}
                onAplicarIe={aplicarIeNoFormulario}
              />
            </>
          ) : (
            <p className="text-sm text-muted-foreground md:col-span-2">
              Cliente marcado como isento de IE. O perfil fiscal da NF-e usará indIEDest=2 (contribuinte
              isento).
            </p>
          )}
          <div className="md:col-span-2 flex flex-col items-stretch gap-2 pt-1 sm:flex-row sm:flex-wrap sm:items-center">
            <CheckboxField control={control} name="ativo" label="Cadastro ativo" />
            <CheckboxField control={control} name="bloqueado" label="Bloqueado para venda" />
          </div>
        </>
      )}

      {tab === 'endereco' && (
        <>
          <p className="text-sm font-semibold text-foreground md:col-span-2">Endereço fiscal</p>
          <AlertaEnderecoFiscal mensagem={enderecoFiscalAlerta} />
          <div>
            <InputField label="CEP" {...cepField} onChange={onCepChange} onBlur={onCepBlur} onKeyDown={onCepKeyDown} />
            <div className="mt-1 flex flex-col items-start gap-1 text-xs sm:flex-row sm:items-center sm:gap-3">
              <span className="break-words text-muted-foreground">
                {cepLookupLoading
                  ? 'Consultando CEP...'
                  : cepLookupMessage ?? 'A consulta ocorre automaticamente ao sair do campo.'}
              </span>
              <button
                type="button"
                className="text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
                onClick={() => void runCepLookup(getValues('cep'), true)}
                disabled={cepLookupLoading}
              >
                Consultar novamente
              </button>
            </div>
          </div>
          <div className="md:col-span-2">
            <InputField label="Logradouro" operationalUpper {...register('logradouro')} />
          </div>
          <InputField label="Número" operationalUpper {...register('numero')} />
          <InputField label="Complemento" operationalUpper {...register('complemento')} />
          <InputField label="Bairro" operationalUpper {...register('bairro')} />
          <InputField label="Cidade" operationalUpper {...register('cidade')} />
          <SelectField label="Estado (UF)" options={ufOptions} {...register('uf')} />
          <ClienteEnderecosEntregaEditor value={enderecosEntrega} onChange={setEnderecosEntrega} />
        </>
      )}

      {tab === 'contatos' && (
        <>
          <InputField label="Contato responsável" operationalUpper {...register('contato_responsavel')} />
          <InputField label="DDD" {...dddField} onChange={onDddChange} maxLength={4} />
          <InputField label="Telefone principal" {...telefoneField} onChange={onTelefoneChange} />
          <InputField
            label="Telefone alternativo"
            {...telefoneAlternativoField}
            onChange={onTelefoneAlternativoChange}
          />
          <InputField label="Celular" {...celularField} onChange={onCelularChange} />
          <InputField label="E-mail" type="email" {...register('email')} error={errors.email?.message} />
          <InputField
            label="E-mail NF"
            type="email"
            {...register('email_nf')}
            error={errors.email_nf?.message}
          />
          <ClienteContatosAdicionaisEditor
            value={contatos}
            erros={contatosErros}
            onChange={(next) => {
              setContatos(next);
              setContatosErros((prev) => (prev.length ? validarContatosCliente(next) : prev));
            }}
          />
        </>
      )}

      {tab === 'nfe-danfe' && (
        <>
          <AlertaEnderecoFiscal mensagem={enderecoFiscalAlerta} />
          <TextareaField
            label="Informações complementares para NF-e/DANFE"
            className="min-h-[200px] md:col-span-2"
            placeholder="Ex.: ENDEREÇO DE ENTREGA RUA MIGUEL LANGONE 341 - HORÁRIO DE ENTREGA DAS 7:00 AS 15:00 HORAS"
            operationalUpper
            {...register('informacoes_complementares_nfe')}
          />
          <p className="text-sm text-muted-foreground md:col-span-2">
            Use este campo para instruções que devem aparecer nos <strong>Dados Adicionais</strong> de toda NF-e
            deste cliente (endereço de entrega, horário de recebimento, doca, contato de recebimento, etc.). O texto
            sai em maiúsculas na DANFE. Não use a aba Observações para isso — aquelas observações são internas do
            ERP.
          </p>
        </>
      )}

      {tab === 'fiscal-financeiro' && (
        <>
          <InputField label="Inscrição Municipal (IM)" operationalUpper {...register('inscricao_municipal')} />
          <InputField label="Suframa" operationalUpper {...register('suframa')} />
          <InputField label="CNAE" operationalUpper {...register('cnae')} />
          <SelectField label="Regime tributário" options={regimeOptions} {...register('regime_tributario')} />
          <InputField label="Banco" operationalUpper {...register('banco')} />
          <InputField label="Agência" operationalUpper {...register('agencia')} />
          <InputField label="Conta (com dígito)" operationalUpper {...register('conta')} />
          <SelectField label="Tipo de conta" options={tipoContaOptions} {...register('tipo_conta')} />
          <InputField
            label="Limite de crédito"
            type="number"
            min={0}
            step="0.01"
            {...register('limite_credito')}
            error={errors.limite_credito?.message}
          />
          <div>
            <InputField
              label="Condição de pagamento"
              placeholder="Ex.: 30 DDL, 30/45 DDL, 30/60/90, à vista"
              operationalUpper
              {...register('condicao_pagamento_texto')}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {condicaoPreview && condicaoPreview.length > 0
                ? `Parcelas interpretadas: ${condicaoPreview.join(', ')} dia(s)`
                : 'Use formatos como 30 DDL, 30/45 DDL, 30/60/90 ou à vista.'}
            </p>
          </div>
          <SelectField
            label="Transportadora padrão"
            options={[{ value: '', label: 'Nenhuma' }, ...transportadoraOptions]}
            {...register('transportadora_padrao_id')}
          />
          <InputField label="Vendedor padrão" operationalUpper {...register('vendedor_padrao')} />
          <TextareaField
            label="Integrações automáticas"
            className="min-h-[90px] md:col-span-2"
            placeholder="Ex.: regras de envio de XML, integração com CRM e observações de automação."
            operationalUpper
            {...register('integracao_texto')}
          />
        </>
      )}

      {tab === 'observacoes' && (
        <>
          <p className="text-sm text-muted-foreground md:col-span-2">
            Informações que saem na NF-e/DANFE são editadas na aba{' '}
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() => setTab('nfe-danfe')}
            >
              NF-e / DANFE
            </button>
            .
          </p>
          <TextareaField
            label="Observações internas (não saem na NF-e)"
            className="min-h-[180px] md:col-span-2"
            placeholder="Uso interno: vendas, financeiro, logística — não imprime na DANFE."
            operationalUpper
            {...register('observacoes')}
          />
        </>
      )}

      {tab === 'historico' && podeVerHistorico && clienteId ? (
        <div className="md:col-span-2">
          <HistoricoAlteracoesPanel
            appLabel="cadastros"
            modelName="cliente"
            objectId={clienteId}
            active={tab === 'historico'}
            enabled={podeVerHistorico}
          />
        </div>
      ) : null}
    </CadastroSection>
  );

  return (
    <CadastroFormShell title="Cliente">
      <form
        onSubmit={handleSubmit(async (values) => {
          const errosContato = validarContatosCliente(contatos);
          if (contatosClienteTemErro(errosContato)) {
            setContatosErros(errosContato);
            setTab('contatos');
            setError('root', {
              message: 'Corrija os contatos adicionais antes de salvar.',
            });
            return;
          }
          setContatosErros([]);
          await onSubmit(toApiPayload(values, enderecosEntrega, contatos));
        })}
        className="space-y-4"
      >
        {errors.root?.message && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {errors.root.message}
          </div>
        )}

        <CadastroTabs tabs={tabItems} value={tab} onValueChange={setTab}>
          {panel}
        </CadastroTabs>

        <div className="sticky bottom-0 z-10 -mx-4 border-t border-border bg-card px-4 py-3 md:-mx-6 md:px-6">
          <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:justify-end">
            <CadastroButton className="w-full sm:w-auto" type="button" variant="outline" onClick={onCancel} disabled={saving}>
              Cancelar
            </CadastroButton>
            <CadastroButton className="w-full sm:w-auto" type="submit" disabled={saving}>
              {saving ? 'Salvando…' : 'Salvar'}
            </CadastroButton>
          </div>
        </div>
      </form>
    </CadastroFormShell>
  );
}
