type FilterOption = { value: string; label: string };

type FilterBarProps = {
  filters: { key: string; label: string; value: string; options: FilterOption[] }[];
  onChange: (key: string, value: string) => void;
};

export function FilterBar({ filters, onChange }: FilterBarProps) {
  if (!filters.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {filters.map((f) => (
        <label key={f.key} className="flex items-center gap-2 text-sm text-muted-foreground">
          {f.label}
          <select
            className="erp-select h-8 py-0 text-sm min-w-[10rem]"
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
