import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

type Key = number | string;

export type AsyncAutocompleteProps<T> = {
  value: Key | null;
  selectedOption?: T | null;
  placeholder?: string;
  disabled?: boolean;
  minChars?: number;
  limit?: number;
  /** Mensagem quando a busca não retorna resultados (padrão: «Nenhum resultado encontrado.»). */
  emptyMessage?: string;
  search: (term: string, limit?: number) => Promise<T[]>;
  getOptionValue: (option: T) => Key;
  getOptionLabel: (option: T) => string;
  /** Se definido, substitui o texto simples da lista (ex.: várias linhas por opção). */
  renderOption?: (option: T) => ReactNode;
  /** Rodapé fixo dentro da lista (ex.: cadastro rápido), após resultados ou mensagem. */
  renderListFooter?: (ctx: { term: string; options: T[]; loading: boolean; error: string | null }) => ReactNode;
  /** Classes extras para o painel da lista (ex.: largura mínima). */
  listBoxClassName?: string;
  inputClassName?: string;
  /** Classes do container externo (ex.: w-full). */
  wrapClassName?: string;
  onChange: (value: Key | null, option?: T | null) => void;
};

export function AsyncAutocomplete<T>({
  value,
  selectedOption = null,
  placeholder = 'Digite para buscar...',
  disabled = false,
  minChars = 2,
  limit = 20,
  emptyMessage = 'Nenhum resultado encontrado.',
  search,
  getOptionValue,
  getOptionLabel,
  renderOption,
  renderListFooter,
  listBoxClassName,
  inputClassName,
  wrapClassName,
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

  const showSelected = !open && value != null && selectedLabel.length > 0;

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
    <div className={cn('min-w-0', wrapClassName)}>
      <div className="flex gap-2 items-start">
        <div className="relative min-w-0 flex-1">
          <input
            className={cn(
              inputClassName ?? 'erp-input mt-1 w-full',
              showSelected && 'truncate',
            )}
            placeholder={placeholder}
            disabled={disabled}
            title={showSelected ? selectedLabel : undefined}
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

          {open ? (
            <div
              className={
                listBoxClassName ??
                'absolute z-50 mt-1 max-h-64 w-full min-w-[16rem] overflow-auto rounded-md border border-border bg-background shadow'
              }
            >
              {term.trim().length < minChars ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">Digite ao menos {minChars} caracteres para buscar.</p>
              ) : loading ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">Buscando...</p>
              ) : error ? (
                <p className="px-3 py-2 text-xs text-destructive">{error}</p>
              ) : options.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">{emptyMessage}</p>
              ) : (
                <ul>
                  {options.map((opt) => {
                    const key = getOptionValue(opt);
                    return (
                      <li key={String(key)}>
                        <button
                          type="button"
                          className="w-full px-3 py-2 text-left text-sm hover:bg-muted whitespace-normal"
                          onClick={() => {
                            onChange(key, opt);
                            setOpen(false);
                            setTerm('');
                          }}
                        >
                          {renderOption ? renderOption(opt) : getOptionLabel(opt)}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {renderListFooter && term.trim().length >= minChars && !loading ? (
                <div className="border-t border-border bg-muted/30">
                  {renderListFooter({ term: term.trim(), options, loading, error })}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {value != null ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm shrink-0 mt-1 h-10 px-2"
            onClick={() => {
              onChange(null, null);
              setTerm('');
              setOptions([]);
              setOpen(false);
            }}
            disabled={disabled}
            title="Limpar seleção"
          >
            Limpar
          </button>
        ) : null}
      </div>
    </div>
  );
}
