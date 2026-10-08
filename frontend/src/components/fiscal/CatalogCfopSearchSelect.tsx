import { useEffect, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import {
  CFOP_SAIDA_OPCOES,
  agruparCfopSaida,
  filtrarCfopBusca,
  labelCfopCatalogo,
  normalizarCfopCodigo,
  opcoesComValorAtual,
  prefixoCfopProvavel,
  type OpcaoCatalogo,
} from '@/lib/catalogosFiscais';

type Props = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  ufOrigem?: string;
  ufDestino?: string;
  placeholder?: string;
  hint?: string;
  /** Catálogo a exibir (padrão: CFOP de saída). */
  opcoes?: OpcaoCatalogo[];
  /** Agrupa por UF só quando o catálogo é de saída. */
  agruparPorUf?: boolean;
};

function renderGrupo(
  titulo: string,
  opcoes: OpcaoCatalogo[],
  onSelect: (codigo: string) => void,
) {
  if (!opcoes.length) return null;
  return (
    <div key={titulo}>
      <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/40 sticky top-0">
        {titulo}
      </p>
      {opcoes.map((o) => (
        <button
          key={o.value}
          type="button"
          className="w-full text-left px-2 py-1.5 text-xs hover:bg-muted/60 border-b border-border/30 last:border-0"
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(o.value);
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const CatalogCfopSearchSelect = ({
  label,
  value,
  onChange,
  ufOrigem = '',
  ufDestino = '',
  placeholder = 'Buscar CFOP por código ou descrição...',
  hint,
  opcoes = CFOP_SAIDA_OPCOES,
  agruparPorUf = true,
}: Props) => {
  const rootRef = useRef<HTMLDivElement>(null);
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState('');

  const codigo = normalizarCfopCodigo(value);
  const descricaoAtual = codigo ? labelCfopCatalogo(codigo, opcoes) : '';
  const foraCatalogo = codigo !== '' && !opcoes.some((o) => o.value === codigo);

  const opcoesFiltradas = useMemo(() => {
    const base = opcoesComValorAtual(codigo, opcoes);
    return filtrarCfopBusca(base, busca);
  }, [busca, codigo, opcoes]);

  const { maisProvaveis, outros } = useMemo(
    () => (agruparPorUf ? agruparCfopSaida(opcoesFiltradas, ufOrigem, ufDestino) : { maisProvaveis: [], outros: opcoesFiltradas }),
    [agruparPorUf, opcoesFiltradas, ufOrigem, ufDestino],
  );

  const prefixoUf = agruparPorUf ? prefixoCfopProvavel(ufOrigem, ufDestino) : null;

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setAberto(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const selecionar = (c: string) => {
    onChange(normalizarCfopCodigo(c));
    setBusca('');
    setAberto(false);
  };

  const limpar = () => {
    onChange('');
    setBusca('');
    setAberto(false);
  };

  const onBlurInput = () => {
    window.setTimeout(() => {
      if (!rootRef.current?.contains(document.activeElement)) {
        const digits = normalizarCfopCodigo(busca);
        if (digits && digits !== codigo) onChange(digits);
        setAberto(false);
      }
    }, 120);
  };

  return (
    <div ref={rootRef} className="relative">
      <label className="erp-label">{label}</label>
      <div className="flex gap-1 mt-1">
        <input
          className="erp-input font-mono flex-1 min-w-0"
          placeholder={placeholder}
          value={aberto ? busca : codigo}
          onChange={(e) => {
            setBusca(e.target.value);
            setAberto(true);
          }}
          onFocus={() => {
            setAberto(true);
            setBusca(codigo);
          }}
          onBlur={onBlurInput}
        />
        {codigo ? (
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm px-2 shrink-0"
            title="Limpar CFOP"
            onClick={limpar}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
      {codigo && !aberto ? (
        <p
          className={`text-[10px] mt-1 leading-snug ${foraCatalogo ? 'text-amber-700 dark:text-amber-400' : 'text-muted-foreground'}`}
        >
          {descricaoAtual}
        </p>
      ) : null}
      {hint ? <p className="text-[10px] text-muted-foreground mt-1">{hint}</p> : null}
      {aberto ? (
        <div className="absolute z-20 left-0 right-0 mt-1 max-h-52 overflow-y-auto rounded border border-border bg-background shadow-md">
          {opcoesFiltradas.length ? (
            prefixoUf ? (
              <>
                {renderGrupo('Mais prováveis', maisProvaveis, selecionar)}
                {renderGrupo('Outros CFOPs', outros, selecionar)}
              </>
            ) : (
              renderGrupo('Catálogo', opcoesFiltradas, selecionar)
            )
          ) : (
            <p className="px-2 py-2 text-xs text-muted-foreground">Nenhum CFOP encontrado.</p>
          )}
        </div>
      ) : null}
    </div>
  );
};
