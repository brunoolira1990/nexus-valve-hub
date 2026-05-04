export function normalizePolegadaInput(input: string): string {
  const raw = (input || '').trim().replace(/"/g, '');
  if (!raw) return '';
  const normalized = raw.replace(/\s+/g, ' ').replace('-', '.').replace(' ', '.');
  return normalized.endsWith('"') ? normalized : `${normalized}"`;
}

export function parsePolegadaToDecimal(input: string): number | null {
  const txt = (input || '').trim().replace(/"/g, '').replace(',', '.').replace('-', '.').replace(' ', '.');
  if (!txt) return null;
  const parts = txt.split('.').filter(Boolean);
  if (parts.length === 1) {
    if (parts[0].includes('/')) {
      const [n, d] = parts[0].split('/');
      const num = Number(n);
      const den = Number(d);
      if (!Number.isFinite(num) || !Number.isFinite(den) || den === 0) return null;
      return num / den;
    }
    const n = Number(parts[0]);
    return Number.isFinite(n) ? n : null;
  }
  if (parts.length === 2 && parts[1].includes('/')) {
    const i = Number(parts[0]);
    const [n, d] = parts[1].split('/');
    const num = Number(n);
    const den = Number(d);
    if (!Number.isFinite(i) || !Number.isFinite(num) || !Number.isFinite(den) || den === 0) return null;
    return i + num / den;
  }
  const n = Number(txt);
  return Number.isFinite(n) ? n : null;
}

export function decimalToMm(decimal: number): number {
  return decimal * 25.4;
}

export function formatMm(value: number): string {
  return value.toFixed(2).replace('.', ',');
}

export function buildPolegadaAliases(input: string, decimal: number): string[] {
  const mm = decimalToMm(decimal);
  const normalized = normalizePolegadaInput(input);
  const base = normalized.replace(/"/g, '');
  const aliases = new Set<string>([
    normalized,
    base,
    base.replace('.', ' '),
    base.replace('.', '-'),
    decimal.toString(),
    decimal.toString().replace('.', ','),
    mm.toFixed(2),
    mm.toFixed(2).replace('.', ','),
  ]);
  if (base === '1/2') {
    aliases.add('meia');
    aliases.add('meio');
    aliases.add('0.5');
    aliases.add('0,5');
  }
  return [...aliases].filter(Boolean);
}
