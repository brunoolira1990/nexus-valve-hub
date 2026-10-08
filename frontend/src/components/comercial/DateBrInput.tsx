import { useEffect, useState } from 'react';
import { formatDateBr, maskDateBrInput, parseDateBrToIso } from '@/lib/dateBr';

type Props = {
  label: string;
  valueIso: string;
  onChangeIso: (iso: string) => void;
  className?: string;
  disabled?: boolean;
};

export function DateBrInput({ label, valueIso, onChangeIso, className, disabled }: Props) {
  const [text, setText] = useState(() => formatDateBr(valueIso));
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setText(formatDateBr(valueIso));
    setErro(null);
  }, [valueIso]);

  const commit = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      setErro(null);
      onChangeIso('');
      return;
    }
    const iso = parseDateBrToIso(trimmed);
    if (!iso) {
      setErro('Data inválida. Use dd/mm/aaaa.');
      return;
    }
    setErro(null);
    onChangeIso(iso);
    setText(formatDateBr(iso));
  };

  return (
    <div className={className}>
      <label className="erp-label">{label}</label>
      <input
        type="text"
        inputMode="numeric"
        className="erp-input mt-1"
        placeholder="dd/mm/aaaa"
        disabled={disabled}
        value={text}
        onChange={(e) => setText(maskDateBrInput(e.target.value))}
        onBlur={() => commit(text)}
      />
      {erro ? <p className="text-[10px] text-destructive mt-1">{erro}</p> : null}
    </div>
  );
}
