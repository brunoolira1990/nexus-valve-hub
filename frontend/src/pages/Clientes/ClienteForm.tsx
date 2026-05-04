import type { ChangeEventHandler, FocusEvent, KeyboardEvent } from 'react';
import { useState } from 'react';
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
import { consultaCep, consultaCnpj } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import { isValidCnpj, normalizeCnpj } from '@/lib/cnpj';
import { digitsOnly, formatCep, formatCnpj, formatPhone } from '@/lib/masks';
import { parsePaymentCondition } from '@/lib/paymentTerms';
import type { Cliente, Transportadora } from '@/types';
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
});

export type ClienteFormInput = z.infer<typeof schema>;

const TAB_ITEMS = [
  { id: 'dados-gerais', label: 'Dados Gerais' },
  { id: 'endereco', label: 'Endereço' },
  { id: 'contatos', label: 'Contatos' },
  { id: 'fiscal-financeiro', label: 'Fiscal / Financeiro' },
  { id: 'observacoes', label: 'Observações' },
] as const;

const regimeOptions = [
  { value: '', label: 'Selecione…' },
  ...REGIMES_CADASTRO.map((r) => ({ value: r, label: r })),
];

const tipoContaOptions = [{ value: '', label: 'Selecione…' }, ...TIPOS_CONTA];

const ufOptions = UFS.map((u) => ({ value: u, label: u }));

function toApiPayload(values: ClienteFormInput): Omit<Cliente, 'id'> {
  return {
    razao_social: values.razao_social,
    nome_fantasia: values.nome_fantasia,
    cnpj: normalizeCnpj(values.cnpj),
    ie: values.ie,
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
  };
}

export function clientToFormValues(c: Partial<Cliente>): ClienteFormInput {
  return {
    razao_social: c.razao_social ?? '',
    nome_fantasia: c.nome_fantasia ?? '',
    cnpj: formatCnpj(c.cnpj ?? ''),
    ddd: digitsOnly(c.ddd ?? '', 4),
    ie: c.ie ?? '',
    inscricao_municipal: c.inscricao_municipal ?? '',
    suframa: c.suframa ?? '',
    cep: formatCep(c.cep ?? ''),
    logradouro: c.logradouro ?? '',
    numero: c.numero ?? '',
    complemento: c.complemento ?? '',
    bairro: c.bairro ?? '',
    cidade: c.cidade ?? '',
    uf: c.uf ?? 'SP',
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
  };
}

type Props = {
  defaultValues: ClienteFormInput;
  transportadoras: Transportadora[];
  onSubmit: (payload: Omit<Cliente, 'id'>) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
};

export function ClienteForm({ defaultValues, transportadoras, onSubmit, onCancel, saving }: Props) {
  const [tab, setTab] = useState<string>(TAB_ITEMS[0].id);
  const [cnpjLookupLoading, setCnpjLookupLoading] = useState(false);
  const [cnpjLookupMessage, setCnpjLookupMessage] = useState<string | null>(null);
  const [lastLookupCnpj, setLastLookupCnpj] = useState<string | null>(null);
  const [cepLookupLoading, setCepLookupLoading] = useState(false);
  const [cepLookupMessage, setCepLookupMessage] = useState<string | null>(null);
  const [lastLookupCep, setLastLookupCep] = useState<string | null>(null);

  const {
    register,
    control,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    getValues,
    formState: { errors },
  } = useForm<ClienteFormInput>({
    resolver: zodResolver(schema),
    defaultValues,
  });
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
      setIfEmpty('logradouro', data.logradouro || '');
      setIfEmpty('complemento', data.complemento || '');
      setIfEmpty('bairro', data.bairro || '');
      setIfEmpty('cidade', data.cidade || '');
      setIfEmpty('uf', data.uf || '');
      if (data.cep) setValue('cep', formatCep(data.cep));
      setLastLookupCep(cep);
      setCepLookupMessage('Endereço encontrado pelo CEP.');
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
    if (cnpj.length !== 14 || !isValidCnpj(cnpj)) return;
    if (cnpjLookupLoading) return;
    if (!force && lastLookupCnpj === cnpj) return;

    clearErrors('root');
    setCnpjLookupMessage(null);
    setCnpjLookupLoading(true);
    try {
      const { data } = await consultaCnpj(cnpj);
      setIfEmpty('razao_social', data.razao_social || '');
      setIfEmpty('nome_fantasia', data.nome_fantasia || '');
      setIfEmpty('logradouro', data.logradouro || '');
      setIfEmpty('numero', data.numero || '');
      setIfEmpty('complemento', data.complemento || '');
      setIfEmpty('bairro', data.bairro || '');
      setIfEmpty('cidade', data.cidade || '');
      setIfEmpty('uf', data.uf || '');
      setIfEmpty('cep', data.cep || '');
      setIfEmpty('telefone', formatPhone(data.telefone || ''));
      setLastLookupCnpj(cnpj);
      setCnpjLookupMessage('Dados do CNPJ consultados com sucesso.');
    } catch (err) {
      const msg = apiErrorMessage(err);
      setCnpjLookupMessage(msg);
      setError('root', { message: msg });
    } finally {
      setCnpjLookupLoading(false);
    }
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
      title={TAB_ITEMS.find((t) => t.id === tab)?.label ?? ''}
      description={
        tab === 'dados-gerais'
          ? 'Base cadastral e identificação principal do cliente.'
          : tab === 'endereco'
            ? 'Localização fiscal e logística para faturamento e entrega.'
            : tab === 'contatos'
              ? 'Canal oficial de relacionamento, cobrança e envio de documentos.'
              : tab === 'fiscal-financeiro'
                ? 'Informações fiscais, bancárias e regras comerciais do cadastro.'
                : 'Observações operacionais para atendimento e equipe interna.'
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
            <div className="mt-1 flex items-center gap-3 text-xs">
              <span className="text-muted-foreground">
                {cnpjLookupLoading
                  ? 'Consultando CNPJ...'
                  : cnpjLookupMessage ?? 'A consulta ocorre automaticamente ao sair do campo.'}
              </span>
              <button
                type="button"
                className="text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
                onClick={() => void runCnpjLookup(getValues('cnpj'), true)}
                disabled={cnpjLookupLoading}
              >
                Consultar novamente
              </button>
            </div>
          </div>
          <InputField label="Inscrição Estadual (IE)" operationalUpper {...register('ie')} />
          <div className="md:col-span-2 flex flex-wrap gap-2 pt-1">
            <CheckboxField control={control} name="ativo" label="Cadastro ativo" />
            <CheckboxField control={control} name="bloqueado" label="Bloqueado para venda" />
          </div>
        </>
      )}

      {tab === 'endereco' && (
        <>
          <div>
            <InputField label="CEP" {...cepField} onChange={onCepChange} onBlur={onCepBlur} onKeyDown={onCepKeyDown} />
            <div className="mt-1 flex items-center gap-3 text-xs">
              <span className="text-muted-foreground">
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
            className="min-h-[90px]"
            placeholder="Ex.: regras de envio de XML, integração com CRM e observações de automação."
            operationalUpper
            {...register('integracao_texto')}
          />
        </>
      )}

      {tab === 'observacoes' && (
        <TextareaField
          label="Observações / recomendações"
          className="min-h-[180px]"
          placeholder="Informações relevantes para vendas, financeiro, logística e pós-venda."
          operationalUpper
          {...register('observacoes')}
        />
      )}
    </CadastroSection>
  );

  return (
    <CadastroFormShell title="Cliente">
      <form
        onSubmit={handleSubmit(async (values) => {
          await onSubmit(toApiPayload(values));
        })}
        className="space-y-4"
      >
        {errors.root?.message && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {errors.root.message}
          </div>
        )}

        <CadastroTabs tabs={TAB_ITEMS} value={tab} onValueChange={setTab}>
          {panel}
        </CadastroTabs>

        <div className="sticky bottom-0 z-10 -mx-4 border-t border-border bg-card px-4 py-3 md:-mx-6 md:px-6">
          <div className="flex justify-end gap-2">
            <CadastroButton type="button" variant="outline" onClick={onCancel} disabled={saving}>
              Cancelar
            </CadastroButton>
            <CadastroButton type="submit" disabled={saving}>
              {saving ? 'Salvando…' : 'Salvar'}
            </CadastroButton>
          </div>
        </div>
      </form>
    </CadastroFormShell>
  );
}
