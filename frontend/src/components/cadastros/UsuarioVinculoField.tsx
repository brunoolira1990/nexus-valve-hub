import { useCallback } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { usuariosService } from '@/services/api/usuarios';
import type { Usuario } from '@/types';

export function labelUsuario(u: Usuario): string {
  const email = (u.email || '').trim();
  return email ? `${u.username} · ${email}` : u.username;
}

export type UsuarioVinculoFieldProps = {
  valueId: number | null;
  selectedUsuario: Usuario | null;
  disabled?: boolean;
  onSelect: (usuario: Usuario) => void;
  onClear: () => void;
};

export function UsuarioVinculoField({
  valueId,
  selectedUsuario,
  disabled,
  onSelect,
  onClear,
}: UsuarioVinculoFieldProps) {
  const buscar = useCallback((term: string, limit?: number) => usuariosService.search(term, limit ?? 25), []);

  return (
    <AsyncAutocomplete<Usuario>
      wrapClassName="w-full"
      value={valueId}
      selectedOption={selectedUsuario}
      placeholder="Buscar usuário/login..."
      disabled={disabled}
      minChars={1}
      limit={25}
      search={buscar}
      getOptionValue={(u) => u.id}
      getOptionLabel={labelUsuario}
      renderOption={(u) => (
        <div>
          <div className="font-medium leading-snug">{u.username}</div>
          {(u.email || '').trim() ? (
            <div className="text-xs text-muted-foreground">{u.email}</div>
          ) : null}
        </div>
      )}
      onChange={(id, opt) => {
        if (id == null || !opt) {
          onClear();
          return;
        }
        onSelect(opt);
      }}
    />
  );
}
