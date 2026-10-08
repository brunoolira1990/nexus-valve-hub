/** Tipos e helpers para listagens paginadas (ERP 4.0.5). */

export type PaginatedResponse<T> = {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type ListQueryParams = {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  limit?: number;
  [key: string]: string | number | boolean | undefined | null;
};

export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS = [20, 50, 100] as const;

export function isPaginatedResponse<T>(data: unknown): data is PaginatedResponse<T> {
  return (
    !!data &&
    typeof data === 'object' &&
    Array.isArray((data as PaginatedResponse<T>).results) &&
    typeof (data as PaginatedResponse<T>).count === 'number'
  );
}

export function unwrapListResults<T>(data: T[] | PaginatedResponse<T> | null | undefined): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (isPaginatedResponse<T>(data)) return data.results;
  return [];
}

export function buildListParams(params?: ListQueryParams): Record<string, string | number> {
  const q: Record<string, string | number> = {};
  if (!params) return q;
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    q[key] = value as string | number;
  });
  return q;
}

export function formatPageRange(page: number, pageSize: number, count: number): string {
  if (count <= 0) return 'Exibindo 0 de 0';
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, count);
  return `Exibindo ${start}–${end} de ${count}`;
}
