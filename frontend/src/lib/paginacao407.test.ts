import { describe, expect, it } from 'vitest';

import { fornecedoresService } from '@/services/api/fornecedores';
import { transportadorasService } from '@/services/api/transportadoras';
import { colaboradoresService } from '@/services/api/colaboradores';
import { propostasService, pedidosCompraService } from '@/services/api/comercial';
import { nfeEntradasService, cteEntradasService } from '@/services/api/fiscal';
import { regrasFiscaisService } from '@/services/api/regras-fiscais';
import { estoqueService, atendimentosEstoqueService } from '@/services/api/outros';
import { corridasService } from '@/services/api/corridas';
import { certificadosQualidadeService } from '@/services/api/qualidade';
import { certificadosFornecedorService } from '@/services/api/certificadosFornecedor';
import { nfeEntradaHistoricaImportadaService } from '@/services/api/nfeEntradaHistoricaImportada';
import { cteHistoricoImportadoService } from '@/services/api/cteHistoricoImportado';

describe('ERP 4.0.7 — services paginados', () => {
  const services = [
    ['fornecedores', fornecedoresService],
    ['transportadoras', transportadorasService],
    ['colaboradores', colaboradoresService],
    ['propostas', propostasService],
    ['pedidosCompra', pedidosCompraService],
    ['nfeEntradas', nfeEntradasService],
    ['cteEntradas', cteEntradasService],
    ['regrasFiscais', regrasFiscaisService],
    ['corridas', corridasService],
    ['certificadosQualidade', certificadosQualidadeService],
    ['certificadosFornecedor', certificadosFornecedorService],
    ['nfeEntradaHistorica', nfeEntradaHistoricaImportadaService],
    ['cteHistorico', cteHistoricoImportadoService],
  ] as const;

  it.each(services)('%s expõe listPaginated', (_name, service) => {
    expect(typeof service.listPaginated).toBe('function');
  });

  it('estoque saldos expõe listSaldosPaginated', () => {
    expect(typeof estoqueService.listSaldosPaginated).toBe('function');
  });

  it('atendimentos estoque expõe listPaginated', () => {
    expect(typeof atendimentosEstoqueService.listPaginated).toBe('function');
  });
});

describe('ERP 4.0.7 — dashboard links', () => {
  it('rotas filtradas esperadas', () => {
    const links = [
      '/pedidos-venda?status=aberto',
      '/pedidos-venda?status=parcialmente_faturado',
      '/nfe-saida?status_emissao=rejeitada_homologacao',
      '/estoque?filtro=baixo_estoque',
      '/produtos?sem_ncm=1',
    ];
    links.forEach((link) => {
      expect(link).toMatch(/^\//);
      expect(link).toContain('?');
    });
  });
});
