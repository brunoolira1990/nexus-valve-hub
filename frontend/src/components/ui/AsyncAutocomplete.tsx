import { useEffect, useMemo, useRef, useState } from 'react';

type Key = number | string;

export type AsyncAutocompleteProps<T> = {
  value: Key | null;
  selectedOption?: T | null;
  placeholder?: string;
  disabled?: boolean;
  minChars?: number;
  limit?: number;
  search: (term: string, limit?: number) => Promise<T[]>;
  getOptionValue: (option: T) => Key;
  getOptionLabel: (option: T) => string;
  onChange: (value: Key | null, option?: T | null) => void;
};

export function AsyncAutocomplete<T>({
  value,
  selectedOption = null,
  placeholder = 'Digite para buscar...',
  disabled = false,
  minChars = 2,
  limit = 20,
  search,
  getOptionValue,
  getOptionLabel,
  onChange,
}: AsyncAutocompleteProps<T>) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState('');
  const [options, setOptions] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reqId = useRef(0);

  const selectedLabel = useMemo(() => {
    if (!selectedOption || value == null) return '';
    return getOptionLabel(selectedOption);
  }, [selectedOption, value, getOptionLabel]);

  useEffect(() => {
    if (!open) return;
    const q = term.trim();
    if (q.length < minChars) {
      setOptions([]);
      setLoading(false);
      setError(null);
      return;
    }
    const current = ++reqId.current;
    setLoading(true);
    setError(null);
    const t = setTimeout(async () => {
      try {
        const list = await search(q, limit);
        if (reqId.current !== current) return;
        setOptions(list);
      } catch {
        if (reqId.current !== current) return;
        setOptions([]);
        setError('Falha ao buscar resultados.');
      } finally {
        if (reqId.current === current) setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [open, term, minChars, limit, search]);

  return (
    <div className="relative">
      <input
        className="erp-input mt-1"
        placeholder={placeholder}
        disabled={disabled}
        value={open ? term : selectedLabel}
        onFocus={() => {
          setOpen(true);
          setTerm('');
        }}
        onChange={(e) => {
          setOpen(true);
          setTerm(e.target.value);
        }}
      />
      {value != null ? (
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm mt-2"
          onClick={() => {
            onChange(null, null);
            setTerm('');
            setOptions([]);
            setOpen(false);
          }}
          disabled={disabled}
        >
          Limpar seleção
        </button>
      ) : null}

      {open ? (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-background shadow">
          {term.trim().length < minChars ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Digite ao menos {minChars} caracteres para buscar.</p>
          ) : loading ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Buscando...</p>
          ) : error ? (
            <p className="px-3 py-2 text-xs text-destructive">{error}</p>
          ) : options.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Nenhum resultado encontrado.</p>
          ) : (
            <ul>
              {options.map((opt) => {
                const key = getOptionValue(opt);
                return (
                  <li key={String(key)}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                      onClick={() => {
                        onChange(key, opt);
                        setOpen(false);
                        setTerm('');
                      }}
                    >
                      {getOptionLabel(opt)}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
