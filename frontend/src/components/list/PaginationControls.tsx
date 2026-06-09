import { formatPageRange, PAGE_SIZE_OPTIONS } from '@/lib/apiList';

type PaginationControlsProps = {
  page: number;
  pageSize: number;
  count: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
};

export function PaginationControls({
  page,
  pageSize,
  count,
  totalPages,
  onPageChange,
  onPageSizeChange,
}: PaginationControlsProps) {
  const canPrev = page > 1;
  const canNext = totalPages > 0 && page < totalPages;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-3 border-t border-border text-sm">
      <span className="text-muted-foreground">{formatPageRange(page, pageSize, count)}</span>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-muted-foreground">
          Por página
          <select
            className="erp-select h-8 py-0 text-sm"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <div className="flex gap-1">
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={!canPrev}
            onClick={() => onPageChange(page - 1)}
          >
            Anterior
          </button>
          <button
            type="button"
            className="erp-btn-outline erp-btn-sm"
            disabled={!canNext}
            onClick={() => onPageChange(page + 1)}
          >
            Próxima
          </button>
        </div>
      </div>
    </div>
  );
}
