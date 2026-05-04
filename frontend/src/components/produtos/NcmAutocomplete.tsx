import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';

export type NcmOption = {
  id: number;
  codigo: string;
  descricao: string;
};

type Props = {
  value: NcmOption | null;
  onChange: (option: NcmOption | null) => void;
  searchNcm: (term: string, limit?: number) => Promise<NcmOption[]>;
  placeholder?: string;
  disabled?: boolean;
  limit?: number;
  minChars?: number;
};

export function NcmAutocomplete({
  value,
  onChange,
  searchNcm,
  placeholder = 'Digite código ou descrição do NCM...',
  disabled,
  limit = 20,
  minChars = 2,
}: Props) {
  return (
    <AsyncAutocomplete<NcmOption>
      value={value?.id ?? null}
      selectedOption={value}
      placeholder={placeholder}
      disabled={disabled}
      limit={limit}
      minChars={minChars}
      search={searchNcm}
      getOptionValue={(opt) => opt.id}
      getOptionLabel={(opt) => `${opt.codigo} — ${opt.descricao}`}
      onChange={(_value, option) => onChange(option ?? null)}
    />
  );
}
