/**
 * AliasesInput — campo de edição de lista livre de strings (aliases / sinônimos).
 *
 * Sem catálogo fixo: o usuário digita e pressiona Enter ou clica em "Adicionar".
 * Remove um item clicando no × ao lado dele.
 */

import { useState, type KeyboardEvent } from 'react';
import { X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

interface AliasesInputProps {
  value: string[];
  onChange: (list: string[]) => void;
  label?: string;
  placeholder?: string;
  hint?: string;
}

export function AliasesInput({
  value,
  onChange,
  label = 'Aliases / sinônimos',
  placeholder = 'Digite um sinônimo e pressione Enter',
  hint = 'Sinônimos usados na busca e correspondência de material.',
}: AliasesInputProps) {
  const [draft, setDraft] = useState('');

  const add = () => {
    const trimmed = draft.trim();
    if (!trimmed || value.includes(trimmed)) return;
    onChange([...value, trimmed]);
    setDraft('');
  };

  const remove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      add();
    }
    if (e.key === 'Backspace' && draft === '' && value.length > 0) {
      remove(value.length - 1);
    }
  };

  return (
    <div className="w-full space-y-2">
      {label && (
        <Label className="text-sm font-medium">{label}</Label>
      )}

      {/* Input + botão */}
      <div className="flex gap-2">
        <Input
          className="h-10 flex-1"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
        />
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm px-3 h-10 shrink-0"
          onClick={add}
        >
          Adicionar
        </button>
      </div>

      {/* Chips */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-1">
          {value.map((alias, i) => (
            <Badge
              key={`${alias}-${i}`}
              variant="secondary"
              className="gap-1 pl-2.5 pr-1.5 py-0.5 text-xs font-normal"
            >
              {alias}
              <button
                type="button"
                aria-label={`Remover ${alias}`}
                className="rounded hover:text-destructive transition-colors"
                onClick={() => remove(i)}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {hint && (
        <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
