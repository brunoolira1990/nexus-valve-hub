import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { DashboardModuloBI, DashboardQueryParams } from '@/services/api/dashboard';
import {
  SESSION_EXPIRED_MESSAGE,
  apiErrorMessage,
  isApiForbidden,
  isApiUnauthorized,
} from '@/services/api/config';

export type DashboardBIModulo =
  | 'comercial'
  | 'fiscal'
  | 'estoque'
  | 'expedicao'
  | 'compras'
  | 'qualidade'
  | 'financeiro';

export type DashboardBIFilters = {
  periodo: string;
  empresa_id: string;
  data_inicio?: string;
  data_fim?: string;
  status?: string;
};

export const DEFAULT_DASHBOARD_BI_FILTERS: DashboardBIFilters = {
  periodo: 'mes_atual',
  empresa_id: '',
};

function filtersFromSearchParams(sp: URLSearchParams): DashboardBIFilters {
  return {
    periodo: sp.get('periodo') || DEFAULT_DASHBOARD_BI_FILTERS.periodo,
    empresa_id: sp.get('empresa_id') || '',
    data_inicio: sp.get('data_inicio') || undefined,
    data_fim: sp.get('data_fim') || undefined,
    status: sp.get('status') || undefined,
  };
}

function filtersToQueryParams(filters: DashboardBIFilters): DashboardQueryParams {
  const params: DashboardQueryParams = { periodo: filters.periodo };
  if (filters.empresa_id) params.empresa_id = filters.empresa_id;
  if (filters.data_inicio) params.data_inicio = filters.data_inicio;
  if (filters.data_fim) params.data_fim = filters.data_fim;
  if (filters.status) params.status = filters.status;
  return params;
}

function filtersToSearchParams(filters: DashboardBIFilters): URLSearchParams {
  const sp = new URLSearchParams();
  if (filters.periodo && filters.periodo !== DEFAULT_DASHBOARD_BI_FILTERS.periodo) {
    sp.set('periodo', filters.periodo);
  }
  if (filters.empresa_id) sp.set('empresa_id', filters.empresa_id);
  if (filters.data_inicio) sp.set('data_inicio', filters.data_inicio);
  if (filters.data_fim) sp.set('data_fim', filters.data_fim);
  if (filters.status) sp.set('status', filters.status);
  return sp;
}

export type DashboardBIFetcher = (params?: DashboardQueryParams) => Promise<DashboardModuloBI>;

export function useDashboardBI(modulo: DashboardBIModulo, fetcher: DashboardBIFetcher) {
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedFilters = useMemo(() => filtersFromSearchParams(searchParams), [searchParams]);
  const [draftFilters, setDraftFilters] = useState<DashboardBIFilters>(appliedFilters);
  const [data, setData] = useState<DashboardModuloBI | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);

  useEffect(() => {
    setDraftFilters(appliedFilters);
  }, [appliedFilters]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setForbidden(false);
    setUnauthorized(false);
    try {
      const result = await fetcher(filtersToQueryParams(appliedFilters));
      setData(result);
    } catch (err) {
      setData(null);
      if (isApiForbidden(err)) {
        setForbidden(true);
        setError(null);
      } else if (isApiUnauthorized(err)) {
        setUnauthorized(true);
        setError(SESSION_EXPIRED_MESSAGE);
      } else {
        setError(
          apiErrorMessage(err, {
            fallback: 'Não foi possível carregar os indicadores do painel.',
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  }, [appliedFilters, fetcher]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyFilters = useCallback(
    (next: DashboardBIFilters) => {
      setSearchParams(filtersToSearchParams(next), { replace: true });
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  return {
    modulo,
    data,
    loading,
    error,
    forbidden,
    unauthorized,
    appliedFilters,
    draftFilters,
    setDraftFilters,
    applyFilters,
    clearFilters,
    reload: load,
    queryParams: filtersToQueryParams(appliedFilters),
  };
}

/** Filtros sincronizados com URL para a home do dashboard (sem fetcher de módulo). */
export function useDashboardHomeFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedFilters = useMemo(() => filtersFromSearchParams(searchParams), [searchParams]);
  const [draftFilters, setDraftFilters] = useState<DashboardBIFilters>(appliedFilters);

  useEffect(() => {
    setDraftFilters(appliedFilters);
  }, [appliedFilters]);

  const applyFilters = useCallback(
    (next: DashboardBIFilters) => {
      setSearchParams(filtersToSearchParams(next), { replace: true });
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const queryParams = useMemo(
    () => filtersToQueryParams(appliedFilters),
    [appliedFilters],
  );

  return {
    appliedFilters,
    draftFilters,
    setDraftFilters,
    applyFilters,
    clearFilters,
    queryParams,
  };
}
