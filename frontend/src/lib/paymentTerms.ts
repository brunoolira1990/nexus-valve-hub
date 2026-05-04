const SPLIT_REGEX = /[\/,\-\s]+/;

function normalize(text: string): string {
  return (text ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/ddl/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function parsePaymentCondition(text: string): number[] {
  const raw = (text ?? '').trim();
  if (!raw) return [];

  const normalized = normalize(raw);
  if (normalized === 'a vista' || normalized === 'avista' || normalized === '0') {
    return [0];
  }

  const parts = normalized.split(SPLIT_REGEX).filter(Boolean);
  if (!parts.length) throw new Error("Condição inválida. Use formatos como '30/45 DDL' ou 'à vista'.");

  const days = parts.map((part) => {
    if (!/^\d+$/.test(part)) throw new Error('Condição inválida. Use apenas números e separadores.');
    const value = Number(part);
    if (value < 0) throw new Error('Dias da condição devem ser maiores ou iguais a zero.');
    return value;
  });

  return days;
}

export function buildDueDates(baseDate: string, days: number[]): string[] {
  if (!baseDate) return [];
  const base = new Date(`${baseDate}T00:00:00`);
  if (Number.isNaN(base.getTime())) return [];
  return days.map((day) => {
    const due = new Date(base);
    due.setDate(due.getDate() + day);
    return due.toISOString().slice(0, 10);
  });
}
