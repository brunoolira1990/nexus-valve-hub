import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiErrorMessage } from '@/services/api/config';
import {
  relatorioFiltrosFromSearchParams,
  relatorioFiltrosToQuery,
  type RelatorioFiltrosState,
} from '@/lib/relatorioFinanceiro';
import { financeiroService } from '@/services/api/financeiro';

type Fetcher<T> = (params: Record<string, string>) => Promise<T>;

export function useRelatorioFinanceiro<T>(fetcher: Fetcher<T>) {
  const [searchParams, setSearchParams] = useSearchParams();
  const filtrosIniciais = useMemo(() => relatorioFiltrosFromSearchParams(searchParams), []);
  const [filtros, setFiltros] = useState<RelatorioFiltrosState>(filtrosIniciais);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => relatorioFiltrosToQuery(filtros), [filtros]);

  const carregar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetcher(query));
    } catch (err) {
      setData(null);
      setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar o relatório.' }));
    } finally {
      setLoading(false);
    }
  }, [fetcher, query]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const aplicarFiltros = (next: RelatorioFiltrosState) => {
    setFiltros(next);
    setSearchParams(new URLSearchParams(relatorioFiltrosToQuery(next)), { replace: true });
  };

  return { data, loading, error, filtros, aplicarFiltros, reload: carregar, query };
}
