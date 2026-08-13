type FilterOption = { value: string; label: string };

type FilterBarProps = {
  filters: { key: string; label: string; value: string; options: FilterOption[] }[];
  onChange: (key: string, value: string) => void;
};

export function FilterBar({ filters, onChange }: FilterBarProps) {
  if (!filters.length) return null;
  return (
    <div className="grid grid-cols-1 gap-3 mb-4 sm:grid-cols-2 xl:flex xl:flex-wrap xl:items-center">
      {filters.map((f) => (
        <label key={f.key} className="flex items-center gap-2 text-sm text-muted-foreground xl:w-auto">
          <span className="shrink-0">{f.label}</span>
          <select
            className="erp-select h-10 py-0 text-sm sm:h-8 xl:w-auto xl:min-w-[10rem]"
            value={f.value}
            onChange={(e) => onChange(f.key, e.target.value)}
          >
            <option value="">Todos</option>
            {f.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}
