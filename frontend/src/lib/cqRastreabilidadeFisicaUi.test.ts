import { describe, expect, it } from 'vitest';

/** Espelha o contrato de avisos de rastreabilidade física no CQ de saída. */
type ItemRastreabilidadeUi = {
  incluir_no_certificado?: boolean;
  corrida?: string;
  lote?: string;
  tem_corrida_lote?: boolean;
  rastreabilidade_motivos?: string[];
  rastreabilidade_avisos?: string[];
  rastreabilidade_mensagens?: string[];
};

const AVISO_FISICA =
  'Rastreabilidade física não vinculada. Isso não impede a emissão do certificado.';

const MOTIVOS_FISICOS = new Set([
  'SEM_CORRIDA_LOTE',
  'ESTOQUE_NAO_APLICADO',
  'SEM_CONFERENCIA_ORIGEM',
  'RASTREABILIDADE_FISICA_OPCIONAL',
]);

function temAvisoRastreabilidadeFisica(itens: ItemRastreabilidadeUi[]): boolean {
  return itens.some(
    (it) =>
      it.incluir_no_certificado !== false &&
      (it.rastreabilidade_motivos?.some((m) => MOTIVOS_FISICOS.has(m)) ||
        it.rastreabilidade_avisos?.some((a) => a.includes('não impede a emissão')) ||
        (!it.tem_corrida_lote && !it.corrida && !it.lote)),
  );
}

function ausenciaEstoqueBloqueiaEmissao(itens: ItemRastreabilidadeUi[]): boolean {
  return itens.some(
    (it) =>
      it.incluir_no_certificado !== false &&
      (it.rastreabilidade_mensagens || []).some((m) =>
        /estoque físico|sem corrida\/lote\.|conferência não vinculada/i.test(m),
      ),
  );
}

describe('CQ — rastreabilidade física informativa', () => {
  it('ausência de estoque/corrida aparece como aviso, não bloqueio', () => {
    const itens: ItemRastreabilidadeUi[] = [
      {
        incluir_no_certificado: true,
        corrida: '',
        lote: '',
        tem_corrida_lote: false,
        rastreabilidade_motivos: ['SEM_CORRIDA_LOTE', 'RASTREABILIDADE_FISICA_OPCIONAL'],
        rastreabilidade_avisos: [AVISO_FISICA, 'Sem corrida/lote de estoque vinculado.'],
        rastreabilidade_mensagens: [],
      },
    ];
    expect(temAvisoRastreabilidadeFisica(itens)).toBe(true);
    expect(ausenciaEstoqueBloqueiaEmissao(itens)).toBe(false);
  });

  it('emissão não fica bloqueada só por rastreabilidade física', () => {
    const itens: ItemRastreabilidadeUi[] = [
      {
        incluir_no_certificado: true,
        corrida: '',
        lote: '',
        rastreabilidade_motivos: ['ESTOQUE_NAO_APLICADO', 'SEM_CONFERENCIA_ORIGEM'],
        rastreabilidade_avisos: [AVISO_FISICA],
        rastreabilidade_mensagens: [],
      },
    ];
    expect(ausenciaEstoqueBloqueiaEmissao(itens)).toBe(false);
  });
});
