import { useState } from 'react';
import { CadastroButton, InputField, SelectField } from '@/components/ui/cadastro';
import { consultaCep } from '@/services/api/consulta';
import { apiErrorMessage } from '@/services/api/config';
import { digitsOnly, formatCep } from '@/lib/masks';
import type { EnderecoEntregaCliente } from '@/types';
import { UFS } from '@/types';

const ufOptions = UFS.map((u) => ({ value: u, label: u }));

function enderecoVazio(): EnderecoEntregaCliente {
  return {
    identificacao: '',
    cep: '',
    logradouro: '',
    numero: '',
    complemento: '',
    bairro: '',
    cidade: '',
    uf: '',
    principal: false,
  };
}

type Props = {
  value: EnderecoEntregaCliente[];
  onChange: (next: EnderecoEntregaCliente[]) => void;
};

export function ClienteEnderecosEntregaEditor({ value, onChange }: Props) {
  const [cepLoadingIdx, setCepLoadingIdx] = useState<number | null>(null);
  const [cepMessage, setCepMessage] = useState<string | null>(null);

  const updateItem = (index: number, patch: Partial<EnderecoEntregaCliente>) => {
    const next = value.map((item, i) => (i === index ? { ...item, ...patch } : item));
    if (patch.principal) {
      onChange(next.map((item, i) => ({ ...item, principal: i === index })));
      return;
    }
    onChange(next);
  };

  const removeItem = (index: number) => {
    const next = value.filter((_, i) => i !== index);
    if (next.length && !next.some((item) => item.principal)) {
      next[0] = { ...next[0], principal: true };
    }
    onChange(next);
  };

  const addItem = () => {
    const item = enderecoVazio();
    if (value.length === 0) item.principal = true;
    onChange([...value, item]);
  };

  const consultarCep = async (index: number, rawCep: string) => {
    const cep = digitsOnly(rawCep, 8);
    if (cep.length !== 8) return;
    setCepLoadingIdx(index);
    setCepMessage(null);
    try {
      const { data } = await consultaCep(cep);
      updateItem(index, {
        cep: formatCep(data.cep || cep),
        logradouro: data.logradouro || '',
        complemento: data.complemento || '',
        bairro: data.bairro || '',
        cidade: data.cidade || '',
        uf: data.uf || '',
      });
      setCepMessage('Endereço preenchido pelo CEP.');
    } catch (err) {
      setCepMessage(apiErrorMessage(err, { fallback: 'Não foi possível consultar o CEP.' }));
    } finally {
      setCepLoadingIdx(null);
    }
  };

  return (
    <div className="md:col-span-2 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Endereços de entrega</h3>
          <p className="text-xs text-muted-foreground">
            Endereço fiscal permanece acima. Use esta seção para locais de entrega estruturados.
          </p>
        </div>
        <CadastroButton type="button" variant="secondary" onClick={addItem}>
          Adicionar endereço
        </CadastroButton>
      </div>

      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum endereço de entrega cadastrado.</p>
      ) : null}

      {value.map((item, index) => (
        <div key={item.id ?? `novo-${index}`} className="rounded-md border border-border p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium">Endereço {index + 1}</span>
            <CadastroButton type="button" variant="outline" onClick={() => removeItem(index)}>
              Remover
            </CadastroButton>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InputField
              label="Identificação / apelido"
              operationalUpper
              value={item.identificacao}
              onChange={(e) => updateItem(index, { identificacao: e.target.value })}
              placeholder="Ex.: Filial Campinas"
            />
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none md:pt-7">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={item.principal}
                onChange={(e) => updateItem(index, { principal: e.target.checked })}
              />
              Endereço de entrega principal
            </label>
            <div>
              <InputField
                label="CEP"
                value={item.cep}
                onChange={(e) => updateItem(index, { cep: formatCep(e.target.value) })}
                onBlur={() => void consultarCep(index, item.cep)}
              />
              {cepLoadingIdx === index ? (
                <p className="mt-1 text-xs text-muted-foreground">Consultando CEP…</p>
              ) : null}
            </div>
            <InputField
              label="Logradouro"
              operationalUpper
              value={item.logradouro}
              onChange={(e) => updateItem(index, { logradouro: e.target.value })}
            />
            <InputField
              label="Número"
              operationalUpper
              value={item.numero}
              onChange={(e) => updateItem(index, { numero: e.target.value })}
            />
            <InputField
              label="Complemento"
              operationalUpper
              value={item.complemento}
              onChange={(e) => updateItem(index, { complemento: e.target.value })}
            />
            <InputField
              label="Bairro"
              operationalUpper
              value={item.bairro}
              onChange={(e) => updateItem(index, { bairro: e.target.value })}
            />
            <InputField
              label="Cidade"
              operationalUpper
              value={item.cidade}
              onChange={(e) => updateItem(index, { cidade: e.target.value })}
            />
            <SelectField
              label="UF"
              options={ufOptions}
              value={item.uf}
              onChange={(e) => updateItem(index, { uf: e.target.value })}
            />
          </div>
        </div>
      ))}

      {cepMessage ? <p className="text-xs text-muted-foreground">{cepMessage}</p> : null}
    </div>
  );
}
