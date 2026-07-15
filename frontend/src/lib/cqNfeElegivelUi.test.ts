import { describe, expect, it } from 'vitest';

/** Espelha o contrato leve de GET /certificados-qualidade/nfes-elegiveis/ */
type NfeElegivelCqOpcao = {
  id: number;
  label_principal: string;
  label_secundario: string;
  ambiente_badge: string | null;
  numero_nfe: string;
  serie_nfe: string;
  elegivel: boolean;
};

function opcaoExibeIdentidadeFiscal(o: NfeElegivelCqOpcao): boolean {
  return (
    o.label_principal.startsWith('NF-e nº') &&
    o.label_principal.includes('Série') &&
    !o.label_principal.includes('RASCUNHO-FAT') &&
    !o.label_principal.includes('FAT-')
  );
}

function opcaoPodeSerVinculadaNovoCq(o: NfeElegivelCqOpcao): boolean {
  return o.elegivel && o.ambiente_badge === 'Produção';
}

describe('CQ — apresentação de NF-e elegível', () => {
  it('usa número fiscal e série como identidade principal', () => {
    const o: NfeElegivelCqOpcao = {
      id: 10,
      label_principal: 'NF-e nº 000012345 — Série 1',
      label_secundario: 'Cliente XYZ · Emissão 14/07/2026',
      ambiente_badge: 'Produção',
      numero_nfe: '12345',
      serie_nfe: '1',
      elegivel: true,
    };
    expect(opcaoExibeIdentidadeFiscal(o)).toBe(true);
    expect(o.id).toBe(10);
  });

  it('rejeita identidade RASCUNHO-FAT', () => {
    const o: NfeElegivelCqOpcao = {
      id: 11,
      label_principal: 'RASCUNHO-FAT-28 - Cliente - Data',
      label_secundario: '',
      ambiente_badge: null,
      numero_nfe: '',
      serie_nfe: '',
      elegivel: false,
    };
    expect(opcaoExibeIdentidadeFiscal(o)).toBe(false);
  });

  it('homologação legada não pode ser vinculada em novo CQ', () => {
    const o: NfeElegivelCqOpcao = {
      id: 12,
      label_principal: 'NF-e nº 000000099 — Série 0',
      label_secundario: 'Cliente XYZ · Emissão 14/07/2026',
      ambiente_badge: 'Homologação',
      numero_nfe: '99',
      serie_nfe: '0',
      elegivel: false,
    };
    expect(opcaoPodeSerVinculadaNovoCq(o)).toBe(false);
  });

  it('produção elegível pode ser vinculada', () => {
    const o: NfeElegivelCqOpcao = {
      id: 13,
      label_principal: 'NF-e nº 000012345 — Série 1',
      label_secundario: 'Cliente XYZ · Emissão 14/07/2026',
      ambiente_badge: 'Produção',
      numero_nfe: '12345',
      serie_nfe: '1',
      elegivel: true,
    };
    expect(opcaoPodeSerVinculadaNovoCq(o)).toBe(true);
  });
});
