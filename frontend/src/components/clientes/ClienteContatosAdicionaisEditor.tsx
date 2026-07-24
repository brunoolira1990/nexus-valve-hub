import { CadastroButton, InputField, SelectField } from '@/components/ui/cadastro';
import {
  MSG_AUXILIAR_CONTATOS_FISCAIS,
  contatoVazioCliente,
  emailContatoValido,
  normalizarEmailContato,
  type ContatoClienteErro,
} from '@/lib/clienteContatosFiscais';
import { digitsOnly, formatPhone } from '@/lib/masks';
import type { ContatoCliente, EnderecoEntregaCliente, TipoContatoCliente } from '@/types';

const TIPO_OPTIONS: { value: TipoContatoCliente; label: string }[] = [
  { value: 'COMERCIAL', label: 'Comercial' },
  { value: 'FINANCEIRO', label: 'Financeiro' },
  { value: 'TECNICO', label: 'Técnico' },
  { value: 'OUTRO', label: 'Outro' },
];

type Props = {
  value: ContatoCliente[];
  onChange: (next: ContatoCliente[]) => void;
  erros?: Array<ContatoClienteErro | null>;
};

export function ClienteContatosAdicionaisEditor({ value, onChange, erros = [] }: Props) {
  const updateItem = (index: number, patch: Partial<ContatoCliente>) => {
    const next = value.map((item, i) => (i === index ? { ...item, ...patch } : item));
    if (patch.principal) {
      const tipo = next[index].tipo;
      onChange(next.map((item, i) => (item.tipo === tipo ? { ...item, principal: i === index } : item)));
      return;
    }
    if (patch.tipo) {
      const tipo = patch.tipo;
      const hasPrincipal = next.some((item, i) => i !== index && item.tipo === tipo && item.principal);
      onChange(
        next.map((item, i) => {
          if (i !== index) return item;
          return { ...item, principal: hasPrincipal ? item.principal : true };
        }),
      );
      return;
    }
    onChange(next);
  };

  const removeItem = (index: number) => {
    const removed = value[index];
    if (removed?.id != null) {
      const ok = window.confirm(
        'Remover este contato do cadastro? Esta ação será aplicada ao salvar o cliente.',
      );
      if (!ok) return;
    }
    const next = value.filter((_, i) => i !== index);
    if (next.length && removed?.principal) {
      const idx = next.findIndex((item) => item.tipo === removed.tipo);
      if (idx >= 0) next[idx] = { ...next[idx], principal: true };
    }
    onChange(next);
  };

  const addItem = () => {
    const item = contatoVazioCliente();
    if (!value.some((c) => c.tipo === item.tipo)) item.principal = true;
    onChange([...value, item]);
  };

  return (
    <div className="md:col-span-2 space-y-4 border-t border-border pt-4 mt-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Contatos adicionais</h3>
          <p className="text-xs text-muted-foreground">
            Contatos por tipo (comercial, financeiro, técnico). Os campos acima permanecem como referência legada.
          </p>
          <p className="text-xs text-muted-foreground mt-1">{MSG_AUXILIAR_CONTATOS_FISCAIS}</p>
        </div>
        <CadastroButton type="button" variant="secondary" onClick={addItem}>
          Adicionar contato
        </CadastroButton>
      </div>

      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum contato adicional cadastrado.</p>
      ) : null}

      {value.map((item, index) => {
        const emailOk = emailContatoValido(item.email);
        const erroEmail = erros[index]?.email;
        const ativo = item.ativo !== false;
        const recebe = Boolean(item.recebe_documentos_fiscais);
        return (
          <div
            key={item.id ?? `novo-${index}`}
            className="rounded-md border border-border p-4 space-y-3"
            data-testid={`contato-adicional-${index}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium">Contato {index + 1}</span>
              <CadastroButton type="button" variant="outline" onClick={() => removeItem(index)}>
                Remover
              </CadastroButton>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SelectField
                label="Tipo"
                options={TIPO_OPTIONS}
                value={item.tipo}
                onChange={(e) => updateItem(index, { tipo: e.target.value as TipoContatoCliente })}
              />
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none md:pt-7">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={item.principal}
                  onChange={(e) => updateItem(index, { principal: e.target.checked })}
                />
                Principal neste tipo
              </label>
              <InputField
                label="Nome"
                operationalUpper
                value={item.nome}
                onChange={(e) => updateItem(index, { nome: e.target.value })}
              />
              <InputField
                label="Telefone"
                value={item.telefone}
                onChange={(e) => updateItem(index, { telefone: formatPhone(e.target.value) })}
              />
              <InputField
                label="Celular"
                value={item.celular}
                onChange={(e) => updateItem(index, { celular: formatPhone(e.target.value) })}
              />
              <InputField
                label="E-mail"
                type="email"
                value={item.email}
                data-testid={`contato-email-${index}`}
                onChange={(e) => {
                  const email = e.target.value;
                  const patch: Partial<ContatoCliente> = { email };
                  if (item.recebe_documentos_fiscais && !emailContatoValido(email)) {
                    patch.recebe_documentos_fiscais = false;
                  }
                  updateItem(index, patch);
                }}
                onBlur={() => {
                  const trimmed = normalizarEmailContato(item.email);
                  if (trimmed !== item.email) updateItem(index, { email: trimmed });
                }}
                error={erroEmail}
              />
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={ativo}
                  onChange={(e) => updateItem(index, { ativo: e.target.checked })}
                  data-testid={`contato-ativo-${index}`}
                />
                Ativo
              </label>
              <label
                className={`flex items-center gap-2 text-sm select-none ${
                  emailOk ? 'cursor-pointer' : 'cursor-not-allowed opacity-70'
                }`}
                title={
                  emailOk
                    ? undefined
                    : 'Informe um e-mail válido antes de marcar para documentos fiscais.'
                }
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={recebe}
                  disabled={!emailOk}
                  onChange={(e) => {
                    if (!emailOk) return;
                    updateItem(index, { recebe_documentos_fiscais: e.target.checked });
                  }}
                  data-testid={`contato-recebe-fiscais-${index}`}
                />
                Recebe documentos fiscais
              </label>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function contatosClienteParaApi(value: ContatoCliente[]): ContatoCliente[] {
  return value.map((item) => ({
    ...item,
    email: normalizarEmailContato(item.email),
    telefone: digitsOnly(item.telefone, 11),
    celular: digitsOnly(item.celular, 11),
    ativo: item.ativo !== false,
    recebe_documentos_fiscais: Boolean(item.recebe_documentos_fiscais),
  }));
}

export function enderecosEntregaParaApi(value: EnderecoEntregaCliente[]): EnderecoEntregaCliente[] {
  return value.map((item) => ({
    ...item,
    cep: digitsOnly(item.cep, 8),
  }));
}
