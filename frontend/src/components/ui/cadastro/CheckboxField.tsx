import type { Control, FieldPath, FieldValues } from 'react-hook-form';
import { Controller } from 'react-hook-form';

type Props<T extends FieldValues> = {
  control: Control<T>;
  name: FieldPath<T>;
  label: string;
};

export function CheckboxField<T extends FieldValues>({ control, name, label }: Props<T>) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
      <Controller
        name={name}
        control={control}
        render={({ field }) => (
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-border"
            checked={field.value}
            onChange={(e) => field.onChange(e.target.checked)}
          />
        )}
      />
      {label}
    </label>
  );
}
