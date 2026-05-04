import type { FocusEvent } from 'react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal } from '@/components/Modal';
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
import { parsePaymentCondition } from '@/lib/paymentTerms';
import type { Fornecedor, Transportadora } from '@/types';
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
  condicao_pagamento_texto: z.string(),
  transportadora_padrao_id: z.string(),
  prazo_entrega: z.coerce.number().min(0),
  ativo: z.boolean(),
  observacoes: z.string(),
});

export type FornecedorFormInput = z.infer<typeof schema>;

const TAB_ITEMS = [
  { id: 'principal', label: 'Dados Principais' },
  { id: 'endereco', label: 'Endereço' },
  { id: 'telefones', label: 'Telefones e E-mail' },
  { id: 'bancario', label: 'Dados Bancários' },
  { id: 'fiscal', label: 'Inscrições, CNAE e Outros' },
  { id: 'integracao', label: 'Integração Automática' },
  { id: 'caracteristicas', label: 'Características' },
  { id: 'recomendacoes', label: 'Recomendações' },
] as const;

const regimeOptions = [
  { value: '', label: 'Selecione…' },
  ...REGIMES_CADASTRO.map((r) => ({ value: r, label: r })),
];

const tipoContaOptions = [{ value: '', label: 'Selecione…' }, ...TIPOS_CONTA];

const ufOptions = UFS.map((u) => ({ value: u, label: u }));

function toApiPayload(values: FornecedorFormInput): Omit<Fornecedor, 'id'> {
  return {
    razao_social: values.razao_social,
    nome_fantasia: values.nome_fantasia,
    cnpj: values.cnpj,
    ie: values.ie,
    logradouro: values.logradouro,
    numero: values.numero,
    complemento: values.complemento,
    bairro: values.bairro,
    cidade: values.cidade,
    uf: values.uf,
    cep: values.cep,
    telefone: values.telefone,
    email: values.email,
    contato_responsavel: values.contato_responsavel,
    observacoes: values.observacoes,
    inscricao_municipal: values.inscricao_municipal,
    suframa: values.suframa,
    email_nf: values.email_nf,
    telefone_alternativo: values.telefone_alternativo,
    celular: values.celular,
    condicao_pagamento_texto: values.condicao_pagamento_texto.trim(),
    transportadora_padrao_id:
      values.transportadora_padrao_id === '' ? null : Number(values.transportadora_padrao_id),
    prazo_entrega: values.prazo_entrega,
    ativo: values.ativo,
    ddd: values.ddd,
    banco: values.banco,
    agencia: values.agencia,
    conta: values.conta,
    tipo_conta: values.tipo_conta,
    cnae: values.cnae,
    regime_tributario: values.regime_tributario,
    integracao_texto: values.integracao_texto,
  };
}

export function fornecedorToFormValues(f: Partial<Fornecedor>): FornecedorFormInput {
  return {
    razao_social: f.razao_social ?? '',
    nome_fantasia: f.nome_fantasia ?? '',
    cnpj: f.cnpj ?? '',
    ddd: f.ddd ?? '',
    ie: f.ie ?? '',
    inscricao_municipal: f.inscricao_municipal ?? '',
    suframa: f.suframa ?? '',
    cep: f.cep ?? '',
    logradouro: f.logradouro ?? '',
    numero: f.numero ?? '',
    complemento: f.complemento ?? '',
    bairro: f.bairro ?? '',
    cidade: f.cidade ?? '',
    uf: f.uf ?? 'SP',
    telefone: f.telefone ?? '',
    telefone_alternativo: f.telefone_alternativo ?? '',
    celular: f.celular ?? '',
    email: f.email ?? '',
    email_nf: f.email_nf ?? '',
    contato_responsavel: f.contato_responsavel ?? '',
    banco: f.banco ?? '',
    agencia: f.agencia ?? '',
    conta: f.conta ?? '',
    tipo_conta: f.tipo_conta ?? '',
    cnae: f.cnae ?? '',
    regime_tributario: f.regime_tributario ?? '',
    integracao_texto: f.integracao_texto ?? '',
    condicao_pagamento_texto: f.condicao_pagamento_texto ?? '',
    transportadora_padrao_id:
      f.transportadora_padrao_id != null ? String(f.transportadora_padrao_id) : '',
    prazo_entrega: f.prazo_entrega ?? 0,
    ativo: f.ativo ?? true,
    observacoes: f.observacoes ?? '',
  };
}

type Props = {
  defaultValues: FornecedorFormInput;
  transportadoras: Transportadora[];
  onSubmit: (payload: Omit<Fornecedor, 'id'>) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
};

export function FornecedorForm({
  defaultValues,
  transportadoras,
  onSubmit,
  onCancel,
  saving,
}: Props) {
  const [tab, setTab] = useState<string>(TAB_ITEMS[0].id);
  const [contactOpen, setContactOpen] = useState(false);
  const [contactDraft, setContactDraft] = useState({
    ddd: '',
    telefone: '',
    telefone_alternativo: '',
    celular: '',
    email: '',
    contato_responsavel: '',
  });

  const {
    register,
    control,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    getValues,
    formState: { errors },
  } = useForm<FornecedorFormInput>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  const openContactModal = () => {
    const v = getValues();
    setContactDraft({
      ddd: v.ddd,
      telefone: v.telefone,
      telefone_alternativo: v.telefone_alternativo,
      celular: v.celular,
      email: v.email,
      contato_responsavel: v.contato_responsavel,
    });
    setContactOpen(true);
  };

  const applyContactModal = () => {
    setValue('ddd', contactDraft.ddd);
    setValue('telefone', contactDraft.telefone);
    setValue('telefone_alternativo', contactDraft.telefone_alternativo);
    setValue('celular', contactDraft.celular);
    setValue('email', contactDraft.email);
    setValue('contato_responsavel', contactDraft.contato_responsavel);
    setContactOpen(false);
  };

  const runCepLookup = async () => {
    const cep = getValues('cep').replace(/\D/g, '');
    if (cep.length !== 8) return;
    clearErrors('root');
    try {
      const { data } = await consultaCep(cep);
      setValue('logradouro', data.logradouro || '');
      setValue('bairro', data.bairro || '');
      setValue('cidade', data.cidade || '');
      setValue('uf', data.uf || '');
      setValue('cep', data.cep || '');
    } catch (err) {
      setError('root', { message: apiErrorMessage(err) });
    }
  };

  const onCepBlur = async (e: FocusEvent<HTMLInputElement>) => {
    const cep = e.target.value.replace(/\D/g, '');
    if (cep.length !== 8) return;
    clearErrors('root');
    try {
      const { data } = await consultaCep(cep);
      setValue('logradouro', data.logradouro || '');
      setValue('bairro', data.bairro || '');
      setValue('cidade', data.cidade || '');
      setValue('uf', data.uf || '');
      setValue('cep', data.cep || '');
    } catch (err) {
      setError('root', { message: apiErrorMessage(err) });
    }
  };

  const onCnpjBlur = async (e: FocusEvent<HTMLInputElement>) => {
    const cnpj = normalizeCnpj(e.target.value);
    if (cnpj.length !== 14) return;
    clearErrors('root');
    try {
      const { data } = await consultaCnpj(cnpj);
      if (data.razao_social) setValue('razao_social', data.razao_social);
      if (data.nome_fantasia) setValue('nome_fantasia', data.nome_fantasia);
      setValue('logradouro', data.logradouro || '');
      setValue('numero', data.numero || '');
      setValue('complemento', data.complemento || '');
      setValue('bairro', data.bairro || '');
      setValue('cidade', data.cidade || '');
      setValue('uf', data.uf || '');
      setValue('cep', data.cep || '');
      setValue('telefone', data.telefone || '');
    } catch (err) {
      setError('root', { message: apiErrorMessage(err) });
    }
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
    <CadastroSection title={TAB_ITEMS.find((t) => t.id === tab)?.label ?? ''}>
      {tab === 'principal' && (
        <>
          <InputField label="Razão Social *" operationalUpper {...register('razao_social')} error={errors.razao_social?.message} />
          <InputField label="Nome Fantasia" operationalUpper {...register('nome_fantasia')} />
          <div className="md:col-span-2 flex flex-col gap-2">
            <InputField label="CNPJ *" {...register('cnpj')} onBlur={onCnpjBlur} error={errors.cnpj?.message} />
            <div className="flex flex-wrap gap-2">
              <CadastroButton
                type="button"
                variant="outline"
                onClick={() => window.alert('Consulta SEFAZ simulada')}
              >
                Pesquisar SEFAZ
              </CadastroButton>
              <CadastroButton type="button" variant="secondary" onClick={openContactModal}>
                Alterar dados de contato
              </CadastroButton>
            </div>
          </div>
        </>
      )}

      {tab === 'endereco' && (
        <>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="flex-1">
              <InputField label="CEP" {...register('cep')} onBlur={onCepBlur} />
            </div>
            <CadastroButton type="button" variant="outline" className="shrink-0" onClick={() => void runCepLookup()}>
              Pesquisar CEP
            </CadastroButton>
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

      {tab === 'telefones' && (
        <>
          <InputField label="DDD" {...register('ddd')} maxLength={4} />
          <InputField label="Telefone" {...register('telefone')} />
          <InputField label="Telefone alternativo" {...register('telefone_alternativo')} />
          <InputField label="Celular" {...register('celular')} />
          <InputField label="E-mail" type="email" {...register('email')} error={errors.email?.message} />
          <InputField
            label="E-mail NF"
            type="email"
            {...register('email_nf')}
            error={errors.email_nf?.message}
          />
          <InputField
            className="md:col-span-2"
            label="Nome do contato (referência)"
            operationalUpper
            {...register('contato_responsavel')}
          />
        </>
      )}

      {tab === 'bancario' && (
        <>
          <InputField label="Banco" operationalUpper {...register('banco')} />
          <InputField label="Agência" operationalUpper {...register('agencia')} />
          <InputField label="Conta (com dígito)" operationalUpper {...register('conta')} />
          <SelectField label="Tipo de conta" options={tipoContaOptions} {...register('tipo_conta')} />
        </>
      )}

      {tab === 'fiscal' && (
        <>
          <InputField label="Inscrição Estadual (IE)" operationalUpper {...register('ie')} />
          <InputField label="Inscrição Municipal (IM)" operationalUpper {...register('inscricao_municipal')} />
          <InputField label="Suframa" operationalUpper {...register('suframa')} />
          <InputField label="CNAE" operationalUpper {...register('cnae')} />
          <SelectField label="Regime tributário" options={regimeOptions} {...register('regime_tributario')} />
        </>
      )}

      {tab === 'integracao' && (
        <TextareaField
          label="Integrações / observações de integração"
          placeholder="Ex.: enviar NF por e-mail, integrar com CRM…"
          operationalUpper
          {...register('integracao_texto')}
        />
      )}

      {tab === 'caracteristicas' && (
        <>
          <InputField
            label="Prazo de entrega (dias)"
            type="number"
            min={0}
            step={1}
            {...register('prazo_entrega')}
            error={errors.prazo_entrega?.message}
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
          <div className="md:col-span-2 pt-2">
            <CheckboxField control={control} name="ativo" label="Ativo" />
          </div>
        </>
      )}

      {tab === 'recomendacoes' && (
        <TextareaField label="Observações / recomendações" operationalUpper {...register('observacoes')} />
      )}
    </CadastroSection>
  );

  return (
    <CadastroFormShell title="Fornecedor">
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

        <div className="flex justify-end gap-2 pt-4 border-t border-border">
          <CadastroButton type="button" variant="outline" onClick={onCancel} disabled={saving}>
            Cancelar
          </CadastroButton>
          <CadastroButton type="submit" disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar'}
          </CadastroButton>
        </div>
      </form>

      <Modal isOpen={contactOpen} onClose={() => setContactOpen(false)} title="Alterar dados de contato" size="md">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InputField
            label="DDD"
            value={contactDraft.ddd}
            onChange={(e) => setContactDraft((d) => ({ ...d, ddd: e.target.value }))}
          />
          <InputField
            label="Telefone"
            value={contactDraft.telefone}
            onChange={(e) => setContactDraft((d) => ({ ...d, telefone: e.target.value }))}
          />
          <InputField
            label="Telefone alternativo"
            value={contactDraft.telefone_alternativo}
            onChange={(e) => setContactDraft((d) => ({ ...d, telefone_alternativo: e.target.value }))}
          />
          <InputField
            label="Celular"
            value={contactDraft.celular}
            onChange={(e) => setContactDraft((d) => ({ ...d, celular: e.target.value }))}
          />
          <InputField
            className="md:col-span-2"
            label="E-mail"
            type="email"
            value={contactDraft.email}
            onChange={(e) => setContactDraft((d) => ({ ...d, email: e.target.value }))}
          />
          <InputField
            className="md:col-span-2"
            label="Nome do contato"
            operationalUpper
            value={contactDraft.contato_responsavel}
            onChange={(e) => setContactDraft((d) => ({ ...d, contato_responsavel: e.target.value }))}
          />
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <CadastroButton type="button" variant="outline" onClick={() => setContactOpen(false)}>
            Fechar
          </CadastroButton>
          <CadastroButton type="button" onClick={applyContactModal}>
            Aplicar
          </CadastroButton>
        </div>
      </Modal>
    </CadastroFormShell>
  );
}
