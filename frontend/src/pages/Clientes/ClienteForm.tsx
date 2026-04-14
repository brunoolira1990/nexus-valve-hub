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
import type { Cliente, CondicaoPagamento, Transportadora } from '@/types';
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
  condicao_pagamento_padrao_id: z.string(),
  transportadora_padrao_id: z.string(),
  vendedor_padrao: z.string(),
  bloqueado: z.boolean(),
  ativo: z.boolean(),
  observacoes: z.string(),
});

export type ClienteFormInput = z.infer<typeof schema>;

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

function toApiPayload(values: ClienteFormInput): Omit<Cliente, 'id'> {
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
    limite_credito: values.limite_credito,
    condicao_pagamento_padrao_id:
      values.condicao_pagamento_padrao_id === '' ? null : Number(values.condicao_pagamento_padrao_id),
    transportadora_padrao_id:
      values.transportadora_padrao_id === '' ? null : Number(values.transportadora_padrao_id),
    vendedor_padrao: values.vendedor_padrao,
    bloqueado: values.bloqueado,
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

export function clientToFormValues(c: Partial<Cliente>): ClienteFormInput {
  return {
    razao_social: c.razao_social ?? '',
    nome_fantasia: c.nome_fantasia ?? '',
    cnpj: c.cnpj ?? '',
    ddd: c.ddd ?? '',
    ie: c.ie ?? '',
    inscricao_municipal: c.inscricao_municipal ?? '',
    suframa: c.suframa ?? '',
    cep: c.cep ?? '',
    logradouro: c.logradouro ?? '',
    numero: c.numero ?? '',
    complemento: c.complemento ?? '',
    bairro: c.bairro ?? '',
    cidade: c.cidade ?? '',
    uf: c.uf ?? 'SP',
    telefone: c.telefone ?? '',
    telefone_alternativo: c.telefone_alternativo ?? '',
    celular: c.celular ?? '',
    email: c.email ?? '',
    email_nf: c.email_nf ?? '',
    limite_credito: c.limite_credito ?? 0,
    condicao_pagamento_padrao_id:
      c.condicao_pagamento_padrao_id != null ? String(c.condicao_pagamento_padrao_id) : '',
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
  condicoes: CondicaoPagamento[];
  transportadoras: Transportadora[];
  onSubmit: (payload: Omit<Cliente, 'id'>) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
};

export function ClienteForm({ defaultValues, condicoes, transportadoras, onSubmit, onCancel, saving }: Props) {
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
  } = useForm<ClienteFormInput>({
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

  const condicaoOptions = condicoes.map((c) => ({ value: String(c.id), label: c.descricao }));
  const transportadoraOptions = transportadoras.map((t) => ({ value: String(t.id), label: t.razao_social }));

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
            {...register('contato_responsavel')}
          />
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
            label="Limite de crédito"
            type="number"
            min={0}
            step="0.01"
            {...register('limite_credito')}
            error={errors.limite_credito?.message}
          />
          <SelectField
            label="Condição de pagamento padrão"
            options={[{ value: '', label: 'Nenhuma' }, ...condicaoOptions]}
            {...register('condicao_pagamento_padrao_id')}
          />
          <SelectField
            label="Transportadora padrão"
            options={[{ value: '', label: 'Nenhuma' }, ...transportadoraOptions]}
            {...register('transportadora_padrao_id')}
          />
          <InputField label="Vendedor padrão" {...register('vendedor_padrao')} />
          <div className="flex flex-col gap-3 md:col-span-2 pt-2">
            <CheckboxField control={control} name="bloqueado" label="Bloqueado" />
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
