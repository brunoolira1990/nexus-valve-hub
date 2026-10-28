import { describe, expect, it } from 'vitest';
import { etiquetaRosca } from './roscaLabel';

/** As 13 linhas de `seed_roscas_conexao_canonicas()` (backend/apps/produtos/roscas_conexao_base.py). */
const CANONICAS: [string, string][] = [
  ['', 'BSP / padrão da família'],
  ['N', 'NPT'],
  ['SW', 'Socket Weld / Solda de encaixe'],
  ['OD', 'OD / dupla anilha'],
  ['ODN', 'OD + NPT'],
  ['U', 'UNF'],
  ['JN', 'JIC x NPT'],
  ['NS', 'NPT x SW'],
  ['FN', 'Fêmea NPT'],
  ['FMN', 'Fêmea-macho NPT'],
  ['MFU', 'Macho-fêmea UNF x BSP'],
  ['FF', 'Fêmea-fêmea'],
  ['MMN', 'Macho-macho NPT'],
];

describe('etiquetaRosca — o rótulo que a ficha de Produto mostra', () => {
  it.each(CANONICAS)('cobertura total do catálogo: nenhuma linha devolve metadado interno', (codigo, descricao) => {
    expect(etiquetaRosca({ codigo, descricao })).not.toMatch(/padr[ãa]o da fam[íi]lia/i);
  });

  // O bug que chegou em localhost: produto com rosca_conexao_id = 1 abria a Edição
  // mostrando a `descricao` crua do catálogo no input bloqueado.
  it('converte a linha-sentinela em BSP, como faz _descricao_rosca_comercial', () => {
    expect(etiquetaRosca({ codigo: '', descricao: 'BSP / padrão da família' })).toBe('BSP');
    expect(etiquetaRosca({ codigo: '', descricao: 'BSP / padrao da familia' })).toBe('BSP');
  });

  it('usa o nome comercial quando o código é apenas a token do SKU', () => {
    expect(etiquetaRosca({ codigo: 'N', descricao: 'NPT' })).toBe('NPT');
    expect(etiquetaRosca({ codigo: 'FN', descricao: 'Fêmea NPT' })).toBe('Fêmea NPT');
  });

  it('fixa SW e mantém o código quando não há descrição', () => {
    expect(etiquetaRosca({ codigo: 'SW', descricao: 'Socket Weld / Solda de encaixe' })).toBe('SW');
    expect(etiquetaRosca({ codigo: 'S', descricao: '' })).toBe('S');
  });

  it('limpa os fragmentos que sobrarem do nome', () => {
    expect(etiquetaRosca({ codigo: 'BSP', descricao: 'BSP default' })).toBe('BSP');
    expect(etiquetaRosca({ codigo: '', descricao: 'Sem rosca' })).toBe('BSP');
    expect(etiquetaRosca({ codigo: '', descricao: '' })).toBe('BSP');
  });

  it('devolve string vazia sem rosca, para a ficha cair na sentinela neutra', () => {
    expect(etiquetaRosca(null)).toBe('');
    expect(etiquetaRosca(undefined)).toBe('');
  });
});
