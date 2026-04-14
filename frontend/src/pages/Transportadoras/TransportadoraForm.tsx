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
import type { Transportadora } from '@/types';
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
  celular: z.string(),
  email: emailOrEmpty,
  email_nf: emailOrEmpty,
  contato: z.string(),
  banco: z.string(),
  agencia: z.string(),
  conta: z.string(),
  tipo_conta: z.string(),
  cnae: z.string(),
  regime_tributario: z.string(),
  integracao_texto: z.string(),
  valor_km: z.coerce.number().min(0),
  placa_padrao: z.string(),
  uf_placa: z.string(),
  ativo: z.boolean(),
  observacoes: z.string(),
});

export type TransportadoraFormInput = z.infer<typeof schema>;

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

function toApiPayload(values: TransportadoraFormInput): Omit<Transportadora, 'id'> {
  return {
    razao_social: values.razao_social,
    nome_fantasia: values.nome_fantasia,
    cnpj: values.cnpj,
    ie: values.ie,
    inscricao_municipal: values.inscricao_municipal,
    logradouro: values.logradouro,
    numero: values.numero,
    complemento: values.complemento,
    bairro: values.bairro,
    cidade: values.cidade,
    uf: values.uf,
    cep: values.cep,
    telefone: values.telefone,
    celular: values.celular,
    email: values.email,
    contato: values.contato,
    placa_padrao: values.placa_padrao,
    uf_placa: values.uf_placa,
    valor_km: values.valor_km,
    ativo: values.ativo,
    observacoes: values.observacoes,
    ddd: values.ddd,
    suframa: values.suframa,
    email_nf: values.email_nf,
    banco: values.banco,
    agencia: values.agencia,
    conta: values.conta,
    tipo_conta: values.tipo_conta,
    cnae: values.cnae,
    regime_tributario: values.regime_tributario,
    integracao_texto: values.integracao_texto,
  };
}

export function transportadoraToFormValues(t: Partial<Transportadora>): TransportadoraFormInput {
  return {
    razao_social: t.razao_social ?? '',
    nome_fantasia: t.nome_fantasia ?? '',
    cnpj: t.cnpj ?? '',
    ddd: t.ddd ?? '',
    ie: t.ie ?? '',
    inscricao_municipal: t.inscricao_municipal ?? '',
    suframa: t.suframa ?? '',
    cep: t.cep ?? '',
    logradouro: t.logradouro ?? '',
    numero: t.numero ?? '',
    complemento: t.complemento ?? '',
    bairro: t.bairro ?? '',
    cidade: t.cidade ?? '',
    uf: t.uf ?? 'SP',
    telefone: t.telefone ?? '',
    celular: t.celular ?? '',
    email: t.email ?? '',
    email_nf: t.email_nf ?? '',
    contato: t.contato ?? '',
    placa_padrao: t.placa_padrao ?? '',
    uf_placa: t.uf_placa ?? 'SP',
    valor_km: t.valor_km ?? 0,
    ativo: t.ativo ?? true,
    observacoes: t.observacoes ?? '',
    banco: t.banco ?? '',
    agencia: t.agencia ?? '',
    conta: t.conta ?? '',
    tipo_conta: t.tipo_conta ?? '',
    cnae: t.cnae ?? '',
    regime_tributario: t.regime_tributario ?? '',
    integracao_texto: t.integracao_texto ?? '',
  };
}

type Props = {
  defaultValues: TransportadoraFormInput;
  onSubmit: (payload: Omit<Transportadora, 'id'>) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
};

export function TransportadoraForm({ defaultValues, onSubmit, onCancel, saving }: Props) {
  const [tab, setTab] = useState<string>(TAB_ITEMS[0].id);
  const [contactOpen, setContactOpen] = useState(false);
  const [contactDraft, setContactDraft] = useState({
    ddd: '',
    telefone: '',
    celular: '',
    email: '',
    contato: '',
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
  } = useForm<TransportadoraFormInput>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  const openContactModal = () => {
    const v = getValues();
    setContactDraft({
      ddd: v.ddd,
      telefone: v.telefone,
      celular: v.celular,
      email: v.email,
      contato: v.contato,
    });
    setContactOpen(true);
  };

  const applyContactModal = () => {
    setValue('ddd', contactDraft.ddd);
    setValue('telefone', contactDraft.telefone);
    setValue('celular', contactDraft.celular);
    setValue('email', contactDraft.email);
    setValue('contato', contactDraft.contato);
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

  const panel = (
    <CadastroSection title={TAB_ITEMS.find((t) => t.id === tab)?.label ?? ''}>
      {tab === 'principal' && (
        <>
          <InputField label="Razão Social *" {...register('razao_social')} error={errors.razao_social?.message} />
          <InputField label="Nome Fantasia" {...register('nome_fantasia')} />
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
            <InputField label="Logradouro" {...register('logradouro')} />
          </div>
          <InputField label="Número" {...register('numero')} />
          <InputField label="Complemento" {...register('complemento')} />
          <InputField label="Bairro" {...register('bairro')} />
          <InputField label="Cidade" {...register('cidade')} />
          <SelectField label="Estado (UF)" options={ufOptions} {...register('uf')} />
        </>
      )}

      {tab === 'telefones' && (
        <>
          <InputField label="DDD" {...register('ddd')} maxLength={4} />
          <InputField label="Telefone" {...register('telefone')} />
          <InputField label="Celular" {...register('celular')} />
          <InputField label="E-mail" type="email" {...register('email')} error={errors.email?.message} />
          <InputField
            label="E-mail NF"
            type="email"
            {...register('email_nf')}
            error={errors.email_nf?.message}
          />
          <InputField className="md:col-span-2" label="Nome do contato (referência)" {...register('contato')} />
        </>
      )}

      {tab === 'bancario' && (
        <>
          <InputField label="Banco" {...register('banco')} />
          <InputField label="Agência" {...register('agencia')} />
          <InputField label="Conta (com dígito)" {...register('conta')} />
          <SelectField label="Tipo de conta" options={tipoContaOptions} {...register('tipo_conta')} />
        </>
      )}

      {tab === 'fiscal' && (
        <>
          <InputField label="Inscrição Estadual (IE)" {...register('ie')} />
          <InputField label="Inscrição Municipal (IM)" {...register('inscricao_municipal')} />
          <InputField label="Suframa" {...register('suframa')} />
          <InputField label="CNAE" {...register('cnae')} />
          <SelectField label="Regime tributário" options={regimeOptions} {...register('regime_tributario')} />
        </>
      )}

      {tab === 'integracao' && (
        <TextareaField
          label="Integrações / observações de integração"
          placeholder="Ex.: enviar NF por e-mail, integrar com CRM…"
          {...register('integracao_texto')}
        />
      )}

      {tab === 'caracteristicas' && (
        <>
          <InputField
            label="Valor do frete por km"
            type="number"
            min={0}
            step="0.01"
            {...register('valor_km')}
            error={errors.valor_km?.message}
          />
          <InputField label="Placa padrão" {...register('placa_padrao')} />
          <SelectField label="UF da placa" options={ufOptions} {...register('uf_placa')} />
          <div className="md:col-span-2 pt-2">
            <CheckboxField control={control} name="ativo" label="Ativo" />
          </div>
        </>
      )}

      {tab === 'recomendacoes' && (
        <TextareaField label="Observações / recomendações" {...register('observacoes')} />
      )}
    </CadastroSection>
  );

  return (
    <CadastroFormShell title="Transportadora">
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
            value={contactDraft.contato}
            onChange={(e) => setContactDraft((d) => ({ ...d, contato: e.target.value }))}
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
