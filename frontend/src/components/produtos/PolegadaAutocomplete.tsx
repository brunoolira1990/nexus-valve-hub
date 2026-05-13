import { useEffect, useMemo, useRef, useState } from 'react';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import { polegadasService } from '@/services/api/produtos';
import type { Polegada } from '@/types';
import { buildPolegadaAliases, decimalToMm, formatMm, normalizePolegadaInput, parsePolegadaToDecimal } from '@/lib/polegadas';

type Props = {
  value: number | null;
  selectedLabel?: string;
  onChange: (id: number | null, option?: Polegada | null) => void;
  placeholder?: string;
  tipoMedida?: 'NPS' | 'OD';
  disabled?: boolean;
  allowCreate?: boolean;
  allowedIds?: number[];
};

const PLACEHOLDER_OD_DEFAULT = 'Digite código, polegada, decimal ou mm. Ex.: 1/2, 0,5, 12,70';
const PLACEHOLDER_NPS_DEFAULT = 'Busque NPS (nominal): código oficial, polegada ou decimal. Ex.: 1/2, 4';

function polegadaLabel(p: Polegada): string {
  if (p.label) return p.label;
  const codigo = p.codigo_oficial || p.codigo || '';
  if (p.valor_mm) return `${codigo} — ${p.descricao} — ${String(p.valor_mm).replace('.', ',')} mm`;
  return `${codigo} — ${p.descricao}`;
}

export function PolegadaAutocomplete({
  value,
  selectedLabel,
  onChange,
  placeholder,
  tipoMedida,
  disabled = false,
  allowCreate = false,
  allowedIds,
}: Props) {
  const placeholderResolved =
    placeholder ?? (tipoMedida === 'NPS' ? PLACEHOLDER_NPS_DEFAULT : PLACEHOLDER_OD_DEFAULT);
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState('');
  const [options, setOptions] = useState<Polegada[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Polegada | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);
  const reqId = useRef(0);
  const minChars = 1;

  const [novo, setNovo] = useState({
    tipo_medida: tipoMedida || 'OD',
    codigo_oficial: '',
    descricao: '',
    valor_decimal: '',
    valor_mm: '',
    aliases: '',
    ativo: true,
    observacoes: '',
  });

  const allowedSet = useMemo(() => new Set(allowedIds || []), [allowedIds]);
  const filtered = useMemo(
    () => (allowedIds?.length ? options.filter((o) => allowedSet.has(o.id)) : options),
    [options, allowedIds, allowedSet],
  );

  useEffect(() => {
    if (!value) {
      setSelected(null);
      return;
    }
    if (selected?.id === value) return;
    void polegadasService
      .getById(value)
      .then((p) => setSelected(p))
      .catch(() => {});
  }, [value, selected?.id]);

  useEffect(() => {
    if (!open) return;
    const q = term.trim();
    if (q.length < minChars) {
      setOptions([]);
      setError(null);
      return;
    }
    const current = ++reqId.current;
    setLoading(true);
    setError(null);
    const t = setTimeout(async () => {
      try {
        const list = await polegadasService.search(q, 20, tipoMedida);
        if (reqId.current !== current) return;
        setOptions(list);
      } catch {
        if (reqId.current !== current) return;
        setOptions([]);
        setError('Falha ao buscar polegadas.');
      } finally {
        if (reqId.current === current) setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [open, term, tipoMedida]);

  const currentLabel = selected ? polegadaLabel(selected) : selectedLabel || '';

  const openCreate = async () => {
    const normalized = normalizePolegadaInput(term);
    const dec = parsePolegadaToDecimal(term);
    const mm = dec != null ? decimalToMm(dec) : null;
    let nextCode = '';
    try {
      const base = await polegadasService.search('', 100, tipoMedida);
      const maxCode = base.reduce((acc, p) => {
        const code = (p.codigo_oficial || p.codigo || '').replace(/\D/g, '');
        const num = Number(code || '0');
        return Number.isFinite(num) ? Math.max(acc, num) : acc;
      }, 0);
      nextCode = String(maxCode + 1).padStart(2, '0');
    } catch {
      nextCode = '';
    }
    setNovo({
      tipo_medida: tipoMedida || 'OD',
      codigo_oficial: nextCode,
      descricao: normalized || term.trim(),
      valor_decimal: dec != null ? String(dec) : '',
      valor_mm: mm != null ? mm.toFixed(2) : '',
      aliases: dec != null ? buildPolegadaAliases(term, dec).join(', ') : '',
      ativo: true,
      observacoes: '',
    });
    setCreateErr(null);
    setCreateOpen(true);
  };

  const salvarNova = async () => {
    setCreateErr(null);
    const decimal = Number((novo.valor_decimal || '').replace(',', '.'));
    const mm = Number((novo.valor_mm || '').replace(',', '.'));
    if (!novo.codigo_oficial.trim()) return setCreateErr('Código oficial é obrigatório.');
    if (!novo.descricao.trim()) return setCreateErr('Polegada/descrição é obrigatória.');
    if (!Number.isFinite(decimal)) return setCreateErr('Valor decimal é obrigatório.');
    if (decimal > 100 || mm > 2540) return setCreateErr('Medida acima do limite operacional de 100". Verifique antes de cadastrar.');
    try {
      const created = await polegadasService.create({
        tipo_medida: novo.tipo_medida || tipoMedida || 'OD',
        codigo_oficial: novo.codigo_oficial.trim(),
        descricao: novo.descricao.trim(),
        valor_decimal: String(decimal),
        valor_mm: Number.isFinite(mm) ? String(mm) : String(decimalToMm(decimal)),
        aliases: novo.aliases,
        ativo: novo.ativo,
        observacoes: novo.observacoes,
      });
      setCreateOpen(false);
      setSelected(created);
      onChange(created.id, created);
      setOpen(false);
      setTerm('');
    } catch (e) {
      const msg = apiErrorMessage(e, { fallback: 'Não foi possível cadastrar a polegada.' });
      if (msg.toLowerCase().includes('já existe') || msg.toLowerCase().includes('unique')) {
        setCreateErr('Já existe uma polegada equivalente. Selecione a opção existente em vez de criar uma nova.');
        return;
      }
      setCreateErr(msg);
    }
  };

  return (
    <div className="relative">
      <input
        className="erp-input mt-1"
        placeholder={placeholderResolved}
        disabled={disabled}
        value={open ? term : currentLabel}
        onFocus={() => {
          setOpen(true);
          setTerm('');
        }}
        onChange={(e) => {
          setOpen(true);
          setTerm(e.target.value);
        }}
      />
      {value != null ? (
        <button
          type="button"
          className="erp-btn-outline erp-btn-sm mt-2"
          onClick={() => {
            onChange(null, null);
            setSelected(null);
            setTerm('');
            setOpen(false);
          }}
          disabled={disabled}
        >
          Limpar seleção
        </button>
      ) : null}
      {open ? (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-background shadow">
          {term.trim().length < minChars ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Digite ao menos {minChars} caractere para buscar.</p>
          ) : loading ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Buscando...</p>
          ) : error ? (
            <p className="px-3 py-2 text-xs text-destructive">{error}</p>
          ) : filtered.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              <p>Nenhuma polegada encontrada.</p>
              {allowCreate ? (
                <button type="button" className="erp-btn-outline erp-btn-sm mt-2" onClick={openCreate}>
                  Cadastrar nova polegada
                </button>
              ) : null}
            </div>
          ) : (
            <ul>
              {filtered.map((opt) => (
                <li key={opt.id}>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => {
                      setSelected(opt);
                      onChange(opt.id, opt);
                      setOpen(false);
                      setTerm('');
                    }}
                  >
                    {polegadaLabel(opt)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Cadastrar nova polegada" size="sm">
        <div className="space-y-3">
          <div>
            <label className="erp-label">Código oficial</label>
            <input className="erp-input mt-1" value={novo.codigo_oficial} onChange={(e) => setNovo((p) => ({ ...p, codigo_oficial: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Polegada/descrição</label>
            <input className="erp-input mt-1" value={novo.descricao} onChange={(e) => setNovo((p) => ({ ...p, descricao: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="erp-label">Valor decimal</label>
              <input
                className="erp-input mt-1"
                value={novo.valor_decimal}
                onChange={(e) => {
                  const v = e.target.value;
                  const d = Number(v.replace(',', '.'));
                  setNovo((p) => ({ ...p, valor_decimal: v, valor_mm: Number.isFinite(d) ? formatMm(decimalToMm(d)) : p.valor_mm }));
                }}
              />
            </div>
            <div>
              <label className="erp-label">Valor em mm</label>
              <input className="erp-input mt-1" value={novo.valor_mm} onChange={(e) => setNovo((p) => ({ ...p, valor_mm: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className="erp-label">Aliases</label>
            <input className="erp-input mt-1" value={novo.aliases} onChange={(e) => setNovo((p) => ({ ...p, aliases: e.target.value }))} />
          </div>
          <div>
            <label className="erp-label">Observações</label>
            <input className="erp-input mt-1" value={novo.observacoes} onChange={(e) => setNovo((p) => ({ ...p, observacoes: e.target.value }))} />
          </div>
          {createErr ? <p className="text-xs text-destructive">{createErr}</p> : null}
          <div className="flex justify-end gap-2">
            <button type="button" className="erp-btn-outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </button>
            <button type="button" className="erp-btn" onClick={salvarNova}>
              Salvar polegada
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
