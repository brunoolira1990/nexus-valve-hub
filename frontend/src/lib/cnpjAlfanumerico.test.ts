import { formatCnpj } from '@/lib/masks';
import { formatCnpjDisplay, isValidCnpj, normalizeCnpj } from '@/lib/cnpj';

describe('CNPJ alfanumérico', () => {
  const cnpj = '00.000.000/E08G-12';

  it('normaliza e valida o CNPJ alfanumérico divulgado pela Receita Federal', () => {
    expect(normalizeCnpj(cnpj)).toBe('00000000E08G12');
    expect(isValidCnpj(cnpj)).toBe(true);
  });

  it('mantém letras na máscara de entrada e na exibição', () => {
    expect(formatCnpj('00000000E08G12')).toBe(cnpj);
    expect(formatCnpjDisplay('00000000E08G12')).toBe(cnpj);
  });
});

export {};
