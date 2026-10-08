/** UX / labels — tela SEFAZ status serviço NF-e 3.6.1 */

import type { Empresa } from '@/types';

const RE_EMITENTE_FIXTURE = /^Emitente\s+\d+/i;
const CNPJS_FIXTURE = new Set(['12345678000199', '00000000000191']);

export type SefazConsultaResumo = {
  ok?: boolean;
  sucesso?: boolean;
  servico_operacional?: boolean;
  c_stat?: string;
  cstat?: string;
  x_motivo?: string;
  motivo?: string;
  erro_tecnico?: string;
  tipo_erro?: string;
  uf?: string;
  ambiente?: string;
  empresa_razao_social?: string;
  endpoint_sefaz?: string;
  diagnostico_http?: {
    http_status?: string;
    content_type?: string;
    html_titulo?: string;
  };
  empresa_fixture_teste?: boolean;
  consulta_sefaz_permitida?: boolean;
  consulta_sefaz_motivo?: string;
};

export function empresaPareceFixture(e: Pick<Empresa, 'razao_social' | 'cnpj'>): boolean {
  const razao = (e.razao_social || '').trim();
  const cnpj = (e.cnpj || '').replace(/\D/g, '');
  return RE_EMITENTE_FIXTURE.test(razao) || CNPJS_FIXTURE.has(cnpj);
}

export function escolherEmpresaInicial(empresas: Empresa[]): number | '' {
  if (!empresas.length) return '';
  const ordenadas = [...empresas].sort((a, b) => {
    const pa = empresaPareceFixture(a) ? 2 : a.certificado_arquivo ? 0 : 1;
    const pb = empresaPareceFixture(b) ? 2 : b.certificado_arquivo ? 0 : 1;
    return pa - pb || a.razao_social.localeCompare(b.razao_social, 'pt-BR');
  });
  return ordenadas[0]?.id ?? '';
}

export function rotuloEmpresaSefaz(e: Empresa): string {
  const base = `${e.razao_social} — ${e.cnpj}`;
  if (empresaPareceFixture(e)) return `${base} (fixture/teste)`;
  if (!e.certificado_arquivo) return `${base} (sem certificado)`;
  return base;
}

export function formatAmbienteUf(ambiente: string | undefined, uf: string | undefined): string {
  const amb = (ambiente || '—').trim();
  const ufVal = (uf || '—').trim();
  return `Ambiente: ${amb} · UF: ${ufVal}`;
}

export function ambienteLabel(homologacao: boolean): string {
  return homologacao ? 'homologação' : 'produção';
}

export function tituloPaginaSefaz(homologacao: boolean): string {
  return `NF-e — SEFAZ (${ambienteLabel(homologacao)})`;
}

export function subtituloPaginaSefaz(homologacao: boolean): string {
  const amb = ambienteLabel(homologacao);
  return `Consulta de status do serviço SEFAZ em ${amb} via PyNFe. Não emite NF-e.`;
}

export function mensagemErroParse(c: SefazConsultaResumo): string {
  const amb = c.ambiente || '—';
  const uf = c.uf || '—';
  const empresa = c.empresa_razao_social ? `, empresa: ${c.empresa_razao_social}` : '';
  const endpoint = c.endpoint_sefaz ? ` Endpoint: ${c.endpoint_sefaz}.` : '';
  const diag = c.diagnostico_http;
  const diagPartes: string[] = [];
  if (diag?.http_status) diagPartes.push(`HTTP ${diag.http_status}`);
  if (diag?.content_type) diagPartes.push(`Content-Type: ${diag.content_type}`);
  if (diag?.html_titulo) diagPartes.push(`título HTML: ${diag.html_titulo}`);
  const diagTxt = diagPartes.length ? ` (${diagPartes.join('; ')}).` : '';
  return (
    `Resposta HTML recebida — não é XML SEFAZ (ambiente: ${amb}, UF: ${uf}${empresa}).${endpoint}${diagTxt} ` +
    'Verifique endpoint SEFAZ, certificado A1, rede, proxy ou firewall.'
  );
}

export function mensagemEmpresaBloqueada(c: SefazConsultaResumo): string {
  return (
    c.consulta_sefaz_motivo ||
    'Empresa de teste ou sem certificado válido para consulta SEFAZ.'
  );
}

export function consultaOk(c: SefazConsultaResumo): boolean {
  if (typeof c.ok === 'boolean') return c.ok;
  if (typeof c.sucesso === 'boolean') return c.sucesso;
  return Boolean(c.servico_operacional);
}

export function cStatExibicao(c: SefazConsultaResumo): string {
  const v = (c.c_stat || c.cstat || '').trim();
  if (v) return v;
  if (!consultaOk(c)) return '';
  return '—';
}

export function motivoExibicao(c: SefazConsultaResumo): string {
  if (c.tipo_erro === 'EMPRESA_BLOQUEADA') {
    return mensagemEmpresaBloqueada(c);
  }
  if (c.tipo_erro === 'PARSE_ERROR' && (c.motivo || c.x_motivo || '').toLowerCase().includes('html')) {
    return mensagemErroParse(c);
  }
  const m = (c.motivo || c.x_motivo || '').trim();
  if (m) return m;
  const e = (c.erro_tecnico || '').trim();
  if (e) return e;
  if (!consultaOk(c)) return 'Falha sem retorno SEFAZ';
  return '—';
}

export function consultaFalhou(c: SefazConsultaResumo): boolean {
  return !consultaOk(c);
}

export function tituloUltimoRetorno(c: SefazConsultaResumo): string {
  if (consultaOk(c)) return 'Último retorno SEFAZ';
  return 'Consulta não concluída';
}

export function resultadoHistoricoLabel(c: SefazConsultaResumo): string {
  if (consultaOk(c)) return 'OK';
  if (c.tipo_erro) return c.tipo_erro;
  return 'Falha';
}

export function erroHistoricoResumo(c: SefazConsultaResumo): string {
  if (consultaOk(c)) return '';
  const e = (c.erro_tecnico || '').trim();
  if (e.length > 60) return `${e.slice(0, 57)}…`;
  return e || motivoExibicao(c);
}
