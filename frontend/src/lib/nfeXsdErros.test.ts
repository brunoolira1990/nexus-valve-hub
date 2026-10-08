/** Testes — formatação de erros XSD NF-e. */

import { describe, expect, it } from 'vitest';
import {
  extrairErrosXsd,
  formatNfeErrosLista,
  formatNfeXsdErro,
  mensagemEmissaoComErrosXsd,
} from '@/lib/nfeXsdErros';

describe('nfeXsdErros', () => {
  it('formata erro XSD estruturado sem [object Object]', () => {
    const texto = formatNfeXsdErro({
      contexto: 'XML_ASSINADO',
      elemento: '/NFe/{http://www.portalfiscal.inf.br/nfe}infNFe/{http://www.portalfiscal.inf.br/nfe}det/{http://www.portalfiscal.inf.br/nfe}imposto/{http://www.portalfiscal.inf.br/nfe}ICMS/{http://www.portalfiscal.inf.br/nfe}ICMS00/{http://www.portalfiscal.inf.br/nfe}CST',
      mensagem: "Element '{http://www.portalfiscal.inf.br/nfe}CST': '500' is not a valid value of the atomic type 'TCstIcms'.",
      linha: 42,
      coluna: 15,
    });
    expect(texto).toContain('XML assinado');
    expect(texto).toContain('Tag CST');
    expect(texto).toContain('TCstIcms');
    expect(texto).not.toContain('[object Object]');
  });

  it('join de lista com objetos retorna texto legível', () => {
    const joined = formatNfeErrosLista([
      { contexto: 'XML_ASSINADO', mensagem: 'Campo inválido', linha: 1 },
    ]);
    expect(joined).toBe('XML assinado: Campo inválido — (linha 1)');
    expect(joined).not.toContain('[object Object]');
  });

  it('extrai erros de validacao_xsd e monta mensagem de emissão', () => {
    const res = {
      etapa: 'VALIDACAO_XSD',
      mensagem: 'Falha na validação XSD local antes da transmissão produção.',
      validacao_xsd: {
        tipo: 'XML_ASSINADO',
        ok: false,
        erros: [
          {
            contexto: 'XML_ASSINADO',
            elemento: '/NFe/{http://www.portalfiscal.inf.br/nfe}infNFe/{http://www.portalfiscal.inf.br/nfe}ide/{http://www.portalfiscal.inf.br/nfe}tpAmb',
            mensagem: "Element 'tpAmb': '2' is not a valid value.",
            linha: 10,
            coluna: 8,
          },
        ],
      },
      sefaz_transmitida: false,
    };
    expect(extrairErrosXsd(res)).toHaveLength(1);
    const msg = mensagemEmissaoComErrosXsd(res);
    expect(msg).toContain('Etapa: VALIDACAO_XSD');
    expect(msg).toContain('Tag tpAmb');
    expect(msg).not.toContain('[object Object]');
  });
});
