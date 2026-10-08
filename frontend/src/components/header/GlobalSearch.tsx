import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Search, X } from 'lucide-react';
import { appContextoService, type BuscaGlobalItem } from '@/services/api/appContexto';
import { apiErrorMessage } from '@/services/api/config';

const MIN_LEN = 2;
const DEBOUNCE_MS = 350;

const GRUPO_ORDEM = ['Clientes', 'Fornecedores', 'Produtos', 'Documentos', 'Financeiro', 'Colaboradores', 'Cadastros', 'Outros'];

function agruparResultados(items: BuscaGlobalItem[]) {
  const map = new Map<string, BuscaGlobalItem[]>();
  for (const item of items) {
    const g = item.grupo || 'Outros';
    if (!map.has(g)) map.set(g, []);
    map.get(g)!.push(item);
  }
  return GRUPO_ORDEM.filter((g) => map.has(g)).map((g) => ({ grupo: g, items: map.get(g)! }));
}

type Props = {
  compact?: boolean;
};

export function GlobalSearch({ compact = false }: Props) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(!compact);
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultados, setResultados] = useState<BuscaGlobalItem[]>([]);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [query]);

  useEffect(() => {
    if (!open || debounced.length < MIN_LEN) {
      setResultados([]);
      setError(null);
      setMensagem(debounced.length > 0 && debounced.length < MIN_LEN ? 'Digite ao menos 2 caracteres.' : null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    void appContextoService
      .buscaGlobal(debounced)
      .then((res) => {
        if (!active) return;
        setResultados(res.resultados || []);
        setMensagem(res.mensagem || null);
      })
      .catch((err) => {
        if (!active) return;
        setResultados([]);
        setError(apiErrorMessage(err, { fallback: 'Não foi possível buscar agora. Tente novamente.' }));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [debounced, open]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const grupos = useMemo(() => agruparResultados(resultados), [resultados]);

  const abrirResultado = useCallback(
    (item: BuscaGlobalItem) => {
      setOpen(false);
      setQuery('');
      navigate(item.url);
    },
    [navigate],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false);
      inputRef.current?.blur();
    }
    if (e.key === 'Enter' && resultados[0]) {
      e.preventDefault();
      abrirResultado(resultados[0]);
    }
  };

  const showPanel = open && (query.trim().length > 0 || loading);

  if (compact && !expanded) {
    return (
      <button
        type="button"
        className="md:hidden erp-btn-ghost erp-btn-sm p-2"
        aria-label="Buscar"
        onClick={() => {
          setExpanded(true);
          setOpen(true);
          window.setTimeout(() => inputRef.current?.focus(), 50);
        }}
      >
        <Search className="h-4 w-4" />
      </button>
    );
  }

  return (
    <div ref={rootRef} className={`relative ${compact ? 'hidden md:block' : ''} min-w-0`}>
      <div className="flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 w-full max-w-xs lg:max-w-sm">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          placeholder="Buscar…"
          aria-label="Busca global"
          aria-expanded={showPanel}
          aria-autocomplete="list"
          className="flex-1 min-w-0 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
        />
        {query ? (
          <button type="button" className="text-muted-foreground hover:text-foreground" aria-label="Limpar busca" onClick={() => setQuery('')}>
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" /> : null}
      </div>

      {showPanel ? (
        <div className="absolute right-0 top-full z-50 mt-1 w-[min(100vw-2rem,24rem)] rounded-md border border-border bg-popover shadow-lg max-h-[min(60vh,420px)] overflow-y-auto">
          {error ? <p className="px-3 py-2 text-sm text-destructive">{error}</p> : null}
          {!error && mensagem && resultados.length === 0 && !loading ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">{mensagem}</p>
          ) : null}
          {!error && !loading && debounced.length >= MIN_LEN && resultados.length === 0 && !mensagem ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">Nenhum resultado encontrado.</p>
          ) : null}
          {grupos.map(({ grupo, items }) => (
            <div key={grupo} className="border-b border-border last:border-0">
              <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/40">
                {grupo}
              </p>
              <ul>
                {items.map((item, idx) => (
                  <li key={`${item.tipo}-${item.url}-${idx}`}>
                    <button
                      type="button"
                      className="w-full text-left px-3 py-2 hover:bg-muted/60 transition-colors"
                      onClick={() => abrirResultado(item)}
                    >
                      <span className="block text-[10px] text-muted-foreground">{item.tipo_label}</span>
                      <span className="block text-sm font-medium truncate">{item.titulo}</span>
                      {item.subtitulo ? (
                        <span className="block text-xs text-muted-foreground truncate">{item.subtitulo}</span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
