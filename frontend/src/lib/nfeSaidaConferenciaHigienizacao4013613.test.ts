import { describe, expect, it } from 'vitest';
import { GRUPO_VALIDACAO_LABELS } from './nfeSaidaConferencia';
import {
  SECAO_HIGIENIZACAO_XML,
  badgeHigienizacaoXml,
  isXmlTransmissaoPreview,
  mapIndFinalParaPayload,
  mapIndPresParaPayload,
  pendenciaHigienizacaoCritica,
  pendenciaIndicadoresNaoConfirmados,
  podeMarcarProntaComHigienizacao,
} from './nfeSaidaConferenciaHigienizacao4013613';

describe('nfeSaidaConferenciaHigienizacao4013613', () => {
  it('GRUPO_VALIDACAO_LABELS inclui higienizacao_xml', () => {
    expect(GRUPO_VALIDACAO_LABELS.higienizacao_xml).toBe('Higienização XML');
    expect(SECAO_HIGIENIZACAO_XML).toContain('Higienização XML');
  });

  it('pendenciaIndicadoresNaoConfirmados', () => {
    expect(pendenciaIndicadoresNaoConfirmados({ indicadores_fiscais_confirmados: false })).toBe(true);
    expect(pendenciaIndicadoresNaoConfirmados({ indicadores_fiscais_confirmados: true })).toBe(false);
  });

  it('isXmlTransmissaoPreview detecta preview', () => {
    expect(isXmlTransmissaoPreview('<infNFe Id="NFePREVIEW13"/>')).toBe(true);
    expect(isXmlTransmissaoPreview('<!-- NÃO TRANSMITIR -->')).toBe(true);
    expect(isXmlTransmissaoPreview('<infNFe Id="NFe35260512345678000199550090000000021000000021"/>')).toBe(false);
  });

  it('badgeHigienizacaoXml estados', () => {
    expect(badgeHigienizacaoXml({ tem_xml_transmissao: true, aprovado: true }).className).toContain('success');
    expect(badgeHigienizacaoXml({ total_pendencias: 2 }).className).toContain('danger');
    expect(badgeHigienizacaoXml({}).className).toContain('warning');
  });

  it('pendenciaHigienizacaoCritica sem xml ou pendências', () => {
    expect(pendenciaHigienizacaoCritica(null)).toBe(true);
    expect(pendenciaHigienizacaoCritica({ tem_xml_transmissao: false })).toBe(true);
    expect(pendenciaHigienizacaoCritica({ tem_xml_transmissao: true, aprovado: true, total_pendencias: 0 })).toBe(
      false,
    );
  });

  it('podeMarcarProntaComHigienizacao bloqueia pendências', () => {
    expect(
      podeMarcarProntaComHigienizacao(true, { indicadores_fiscais_confirmados: false }, { aprovado: true }),
    ).toBe(false);
    expect(
      podeMarcarProntaComHigienizacao(
        true,
        { indicadores_fiscais_confirmados: true },
        { tem_xml_transmissao: true, aprovado: true, total_pendencias: 0 },
      ),
    ).toBe(true);
    expect(podeMarcarProntaComHigienizacao(false, { indicadores_fiscais_confirmados: true }, { aprovado: true })).toBe(
      false,
    );
  });

  it('mapIndFinal e mapIndPres', () => {
    expect(mapIndFinalParaPayload(true)).toBe('1');
    expect(mapIndFinalParaPayload(false)).toBe('0');
    expect(mapIndPresParaPayload('2')).toBe('2');
  });
});
