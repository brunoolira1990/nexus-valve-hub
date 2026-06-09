import { useCallback, useEffect, useRef, useState } from 'react';

import {
  DEFAULT_PAGE_SIZE,
  type ListQueryParams,
  type PaginatedResponse,
} from '@/lib/apiList';
import { apiErrorMessage } from '@/services/api/config';

type UsePaginatedListOptions<T> = {
  fetchPage: (params: ListQueryParams) => Promise<PaginatedResponse<T>>;
  initialPageSize?: number;
  debounceMs?: number;
  initialFilters?: Record<string, string>;
  enabled?: boolean;
};

export function usePaginatedList<T>({
  fetchPage,
  initialPageSize = DEFAULT_PAGE_SIZE,
  debounceMs = 400,
  initialFilters = {},
  enabled = true,
}: UsePaginatedListOptions<T>) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [ordering, setOrdering] = useState<string | undefined>();
  const [filters, setFilters] = useState<Record<string, string>>(initialFilters);
  const [data, setData] = useState<PaginatedResponse<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetchRef = useRef(fetchPage);
  fetchRef.current = fetchPage;

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search.trim()), debounceMs);
    return () => window.clearTimeout(t);
  }, [search, debounceMs]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, pageSize, ordering, filters]);

  const reload = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params: ListQueryParams = {
        page,
        page_size: pageSize,
        ...filters,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (ordering) params.ordering = ordering;
      const response = await fetchRef.current(params);
      setData(response);
      if (response.total_pages > 0 && page > response.total_pages) {
        setPage(response.total_pages);
      }
    } catch (err) {
      setData(null);
      setError(apiErrorMessage(err, { fallback: 'Não foi possível carregar os dados. Tente novamente.' }));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, ordering, filters, enabled]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const setFilter = useCallback((key: string, value: string) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (!value) delete next[key];
      else next[key] = value;
      return next;
    });
  }, []);

  return {
    items: data?.results ?? [],
    count: data?.count ?? 0,
    page,
    pageSize,
    totalPages: data?.total_pages ?? 0,
    search,
    setSearch,
    ordering,
    setOrdering,
    filters,
    setFilter,
    setFilters,
    setPage,
    setPageSize,
    loading,
    error,
    reload,
  };
}
