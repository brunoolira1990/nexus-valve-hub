import { Plus, Search } from 'lucide-react';

interface PageHeaderProps {
  title: string;
  onAdd?: () => void;
  addLabel?: string;
  searchValue?: string;
  onSearch?: (val: string) => void;
}

export const PageHeader = ({ title, onAdd, addLabel = 'Novo', searchValue, onSearch }: PageHeaderProps) => (
  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
    <h1 className="text-2xl font-bold text-foreground">{title}</h1>
    <div className="flex items-center gap-3">
      {onSearch && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Buscar..."
            value={searchValue}
            onChange={e => onSearch(e.target.value)}
            className="erp-input pl-9 w-48"
          />
        </div>
      )}
      {onAdd && (
        <button onClick={onAdd} className="erp-btn-primary">
          <Plus className="h-4 w-4" />
          {addLabel}
        </button>
      )}
    </div>
  </div>
);
