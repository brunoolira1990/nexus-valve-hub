import { CadastroButton, InputField, SelectField } from '@/components/ui/cadastro';
import { digitsOnly, formatPhone } from '@/lib/masks';
import type { ContatoCliente, EnderecoEntregaCliente, TipoContatoCliente } from '@/types';

const TIPO_OPTIONS: { value: TipoContatoCliente; label: string }[] = [
  { value: 'COMERCIAL', label: 'Comercial' },
  { value: 'FINANCEIRO', label: 'Financeiro' },
  { value: 'TECNICO', label: 'Técnico' },
  { value: 'OUTRO', label: 'Outro' },
];

function contatoVazio(): ContatoCliente {
  return {
    tipo: 'COMERCIAL',
    nome: '',
    telefone: '',
    celular: '',
    email: '',
    principal: false,
  };
}

type Props = {
  value: ContatoCliente[];
  onChange: (next: ContatoCliente[]) => void;
};

export function ClienteContatosAdicionaisEditor({ value, onChange }: Props) {
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
    const next = value.filter((_, i) => i !== index);
    if (next.length && removed?.principal) {
      const idx = next.findIndex((item) => item.tipo === removed.tipo);
      if (idx >= 0) next[idx] = { ...next[idx], principal: true };
    }
    onChange(next);
  };

  const addItem = () => {
    const item = contatoVazio();
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
        </div>
        <CadastroButton type="button" variant="secondary" onClick={addItem}>
          Adicionar contato
        </CadastroButton>
      </div>

      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum contato adicional cadastrado.</p>
      ) : null}

      {value.map((item, index) => (
        <div key={item.id ?? `novo-${index}`} className="rounded-md border border-border p-4 space-y-3">
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
              onChange={(e) => updateItem(index, { email: e.target.value })}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function contatosClienteParaApi(value: ContatoCliente[]): ContatoCliente[] {
  return value.map((item) => ({
    ...item,
    telefone: digitsOnly(item.telefone, 11),
    celular: digitsOnly(item.celular, 11),
  }));
}

export function enderecosEntregaParaApi(value: EnderecoEntregaCliente[]): EnderecoEntregaCliente[] {
  return value.map((item) => ({
    ...item,
    cep: digitsOnly(item.cep, 8),
  }));
}
