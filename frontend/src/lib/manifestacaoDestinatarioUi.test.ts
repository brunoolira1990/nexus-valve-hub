import { describe, expect, it } from 'vitest';

import { xmlBadgeFromManifestacaoStatus } from '@/lib/centralDfeUi';
import {
  badgeXml,
  statusManifestacaoExibicao,
  statusXmlExibicao,
} from '@/lib/manifestacaoDestinatarioUi';

describe('manifestacaoDestinatarioUi', () => {
  it('não usa badge processando para XML DISPONIVEL', () => {
    expect(badgeXml('DISPONIVEL')).toBe('pronta');
    expect(xmlBadgeFromManifestacaoStatus('DISPONIVEL')).toBe('pronta');
  });

  it('exibe label XML disponível coerente com estado consolidado', () => {
    const exibicao = statusXmlExibicao(
      {
        status_xml: 'DISPONIVEL',
        status_xml_label: 'XML disponível',
      },
      {
        tipo_documento: 'NFE_ENTRADA',
        status_entrada: 'PENDENTE_ENTRADA',
        xml_armazenado: false,
        xml_status: 'DISPONIVEL',
        xml_status_label: 'XML disponível',
      },
    );

    expect(exibicao.label).toBe('XML disponível');
    expect(exibicao.badge).not.toBe('processando');
    expect(exibicao.badge).toBe('pronta');
  });

  it('usa label da manifestação em vez do token do badge', () => {
    const exibicao = statusManifestacaoExibicao(
      {
        status_manifestacao: 'CIENTE',
        status_manifestacao_label: 'Ciência da emissão',
      },
      { tipo_documento: 'NFE_ENTRADA' },
    );

    expect(exibicao.label).toBe('Ciência da emissão');
    expect(exibicao.badge).toBe('processando');
  });
});
