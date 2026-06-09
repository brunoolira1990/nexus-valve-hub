import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apuracaoService } from '@/services/api/outros';
import { empresasService } from '@/services/api/empresas';
import { apiErrorMessage } from '@/services/api/config';
import type {
  ApuracaoDiagnostico,
  ApuracaoDiagnosticoFontes,
  ApuracaoDiagnosticoReforma,
  ApuracaoEfdContribuicoes,
  ApuracaoEfdIcmsIpi,
  ApuracaoFiscalAcumulo,
  ApuracaoFiscalAlerta,
  ApuracaoFiscalFontes,
  ApuracaoFiscalPayload,
  ApuracaoReformaDetalhe,
  ApuracaoReformaTributaria,
  Empresa,
} from '@/types';

type TabId =
  | 'resumo'
  | 'icms_ipi'
  | 'pis_cofins'
  | 'reforma'
  | 'efd_icms'
  | 'efd_contrib'
  | 'agrupamentos'
  | 'alertas'
  | 'info_tecnica';

const TABS: { id: TabId; label: string }[] = [
  { id: 'resumo', label: 'Resumo' },
  { id: 'icms_ipi', label: 'ICMS/IPI' },
  { id: 'pis_cofins', label: 'PIS/COFINS' },
  { id: 'reforma', label: 'Reforma Tributária' },
  { id: 'efd_icms', label: 'Base EFD ICMS/IPI' },
  { id: 'efd_contrib', label: 'Base EFD Contribuições' },
  { id: 'agrupamentos', label: 'Agrupamentos' },
  { id: 'alertas', label: 'Alertas' },
  { id: 'info_tecnica', label: 'Informações técnicas' },
];

const SPED_TXT_TOOLTIP =
  'Disponível após validação da base fiscal e parametrização SPED. Em preparação nesta versão.';

/** Exibe ISO yyyy-mm-dd como dd/mm/yyyy (apenas a parte da data). */
function formatISODatePtBR(iso: string | undefined | null): string {
  if (!iso || String(iso).length < 10) return '—';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  if (!y || !m || !d) return String(iso);
  return `${d}/${m}/${y}`;
}

function isoDate10(v: unknown): string {
  const s = String(v ?? '').trim();
  if (!s) return '';
  return s.replace(/T.*/, '').slice(0, 10);
}

/** Competência fiscal: mensal, trimestral, semestral, anual ou intervalo livre. */
type PeriodoTipoApuracao = 'MENSAL' | 'TRIMESTRAL' | 'SEMESTRAL' | 'ANUAL' | 'PERSONALIZADO';

const MESES_PT = [
  '',
  'Janeiro',
  'Fevereiro',
  'Março',
  'Abril',
  'Maio',
  'Junho',
  'Julho',
  'Agosto',
  'Setembro',
  'Outubro',
  'Novembro',
  'Dezembro',
] as const;

/** Último dia do mês (1–12), respeita ano bissexto. */
function lastDayOfMonth(ano: number, mes: number): number {
  return new Date(ano, mes, 0).getDate();
}

function calcularPeriodoMensal(ano: number, mes: number): { data_inicio: string; data_fim: string } {
  const m = Math.min(12, Math.max(1, Math.floor(mes)));
  const y = Math.floor(ano);
  const mi = String(m).padStart(2, '0');
  const ult = lastDayOfMonth(y, m);
  return {
    data_inicio: `${y}-${mi}-01`,
    data_fim: `${y}-${mi}-${String(ult).padStart(2, '0')}`,
  };
}

function calcularPeriodoTrimestral(ano: number, trimestre: number): { data_inicio: string; data_fim: string } {
  const t = Math.min(4, Math.max(1, Math.floor(trimestre)));
  const y = Math.floor(ano);
  const startMonth = (t - 1) * 3 + 1;
  const endMonth = startMonth + 2;
  const mi0 = String(startMonth).padStart(2, '0');
  const mi1 = String(endMonth).padStart(2, '0');
  const ult = lastDayOfMonth(y, endMonth);
  return {
    data_inicio: `${y}-${mi0}-01`,
    data_fim: `${y}-${mi1}-${String(ult).padStart(2, '0')}`,
  };
}

function calcularPeriodoSemestral(ano: number, semestre: number): { data_inicio: string; data_fim: string } {
  const s = Math.min(2, Math.max(1, Math.floor(semestre)));
  const y = Math.floor(ano);
  if (s === 1) {
    return {
      data_inicio: `${y}-01-01`,
      data_fim: `${y}-06-30`,
    };
  }
  return {
    data_inicio: `${y}-07-01`,
    data_fim: `${y}-12-31`,
  };
}

function calcularPeriodoAnual(ano: number): { data_inicio: string; data_fim: string } {
  const y = Math.floor(ano);
  return {
    data_inicio: `${y}-01-01`,
    data_fim: `${y}-12-31`,
  };
}

/** Se `data_inicio`/`data_fim` forem exatamente o 1º e o último dia do mesmo mês, retorna competência. */
function interpretarDatasComoMesFiscal(
  data_inicio: string,
  data_fim: string,
): { mes: number; ano: number } | null {
  const a = isoDate10(data_inicio);
  const b = isoDate10(data_fim);
  if (a.length < 10 || b.length < 10) return null;
  const [y1s, m1s, d1s] = a.split('-');
  const [y2s, m2s, d2s] = b.split('-');
  const y1 = Number(y1s);
  const m1 = Number(m1s);
  const d1 = Number(d1s);
  const y2 = Number(y2s);
  const m2 = Number(m2s);
  const d2 = Number(d2s);
  if (!Number.isFinite(y1) || !Number.isFinite(m1) || !Number.isFinite(d1)) return null;
  if (!Number.isFinite(y2) || !Number.isFinite(m2) || !Number.isFinite(d2)) return null;
  if (y1 !== y2 || m1 !== m2 || d1 !== 1) return null;
  if (d2 !== lastDayOfMonth(y1, m1)) return null;
  return { mes: m1, ano: y1 };
}

type PeriodoApuracaoUi = {
  tipo: PeriodoTipoApuracao;
  mes: number;
  ano: number;
  trimestre: number;
  semestre: number;
  data_inicio: string;
  data_fim: string;
};

function resolvePeriodoParaDatas(p: PeriodoApuracaoUi): { data_inicio: string; data_fim: string } {
  switch (p.tipo) {
    case 'MENSAL':
      return calcularPeriodoMensal(p.ano, p.mes);
    case 'TRIMESTRAL':
      return calcularPeriodoTrimestral(p.ano, p.trimestre);
    case 'SEMESTRAL':
      return calcularPeriodoSemestral(p.ano, p.semestre);
    case 'ANUAL':
      return calcularPeriodoAnual(p.ano);
    case 'PERSONALIZADO':
    default:
      return {
        data_inicio: isoDate10(p.data_inicio) || p.data_inicio,
        data_fim: isoDate10(p.data_fim) || p.data_fim,
      };
  }
}

function formatarRotuloPeriodoSelecionado(p: PeriodoApuracaoUi): string {
  switch (p.tipo) {
    case 'MENSAL':
      return `${MESES_PT[p.mes] ?? 'Mês'}/${p.ano}`;
    case 'TRIMESTRAL':
      return `${p.trimestre}º trimestre/${p.ano}`;
    case 'SEMESTRAL':
      return `${p.semestre}º semestre/${p.ano}`;
    case 'ANUAL':
      return `Ano de ${p.ano}`;
    case 'PERSONALIZADO':
    default:
      return 'Personalizado';
  }
}

/** Metadados opcionais de competência (a API pode ignorar chaves não usadas). */
function montarExtrasPeriodoQuery(p: PeriodoApuracaoUi): Record<string, string | number> {
  const out: Record<string, string | number> = {
    periodo_tipo: p.tipo,
    periodo_rotulo: formatarRotuloPeriodoSelecionado(p),
    ano: p.ano,
  };
  if (p.tipo === 'MENSAL') out.mes = p.mes;
  if (p.tipo === 'TRIMESTRAL') out.trimestre = p.trimestre;
  if (p.tipo === 'SEMESTRAL') out.semestre = p.semestre;
  return out;
}

const AGRUPAMENTO_LABELS: { key: keyof NonNullable<ApuracaoFiscalPayload['agrupamentos']>; titulo: string }[] = [
  { key: 'por_cfop', titulo: 'Por CFOP' },
  { key: 'por_ncm', titulo: 'Por NCM' },
  { key: 'por_cst_icms', titulo: 'Por CST ICMS' },
  { key: 'por_cst_pis', titulo: 'Por CST PIS' },
  { key: 'por_cst_cofins', titulo: 'Por CST COFINS' },
  { key: 'por_participante', titulo: 'Por participante' },
  { key: 'por_produto', titulo: 'Por produto' },
  { key: 'por_modelo_documento', titulo: 'Por modelo documento' },
  { key: 'por_uf', titulo: 'Por UF' },
];

function fmtMoney(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function fmtMoneyPlain(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function baseCbsIbsDisplay(d?: ApuracaoReformaDetalhe) {
  if (!d) return '—';
  const b = d.base_cbs ?? d.base_ibs;
  return fmtMoney(b);
}

function ReformaBlocoOrigem({
  titulo,
  subtitulo,
  d,
}: {
  titulo: string;
  subtitulo?: string;
  d?: ApuracaoReformaDetalhe;
}) {
  if (!d) {
    return (
      <section className="rounded-2xl border border-dashed border-border/70 bg-muted/10 p-6 md:p-7 space-y-2 shadow-sm">
        <h3 className="text-base font-semibold text-foreground">{titulo}</h3>
        {subtitulo ? <p className="text-xs text-muted-foreground">{subtitulo}</p> : null}
        <p className="text-sm text-muted-foreground pt-2">Nenhum valor CBS/IBS encontrado para esta origem no período.</p>
      </section>
    );
  }
  const ibsTot = d.valor_ibs_total ?? (d.valor_ibs_uf ?? 0) + (d.valor_ibs_municipio ?? 0);
  const haMovimento =
    (d.valor_cbs ?? 0) > 0 ||
    ibsTot > 0 ||
    (d.valor_is ?? 0) > 0 ||
    (d.itens_com_tags_ibscbs ?? 0) > 0 ||
    (d.notas_com_ibscbstot ?? 0) > 0 ||
    (d.cte_com_tags_ibscbs ?? 0) > 0 ||
    (d.notas_com_reforma_e_outros_json ?? 0) > 0;
  const tagsComValoresZerados =
    ((d.itens_com_tags_ibscbs ?? 0) > 0 && (d.itens_com_valores_ibscbs ?? 0) === 0 && (d.valor_cbs ?? 0) === 0 && ibsTot === 0 && (d.valor_is ?? 0) === 0) ||
    (d.notas_tags_ibscbs_zeradas ?? 0) > 0;

  return (
    <section className="rounded-2xl border border-border/60 bg-card p-6 md:p-7 space-y-4 shadow-sm ring-1 ring-border/20">
      <div>
        <h3 className="text-base font-semibold text-foreground">{titulo}</h3>
        {subtitulo ? <p className="text-xs text-muted-foreground mt-1">{subtitulo}</p> : null}
      </div>
      {!haMovimento ? (
        <p className="text-sm text-muted-foreground">Nenhum valor CBS/IBS encontrado para esta origem no período.</p>
      ) : (
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-3 sm:col-span-2 py-1 border-b border-border/40">
            <dt className="text-muted-foreground">Base CBS/IBS</dt>
            <dd className="font-mono tabular-nums font-medium text-foreground">{baseCbsIbsDisplay(d)}</dd>
          </div>
          <div className="flex justify-between gap-3 py-0.5">
            <dt className="text-muted-foreground">CBS</dt>
            <dd className="font-mono font-semibold tabular-nums text-foreground">{fmtMoney(d.valor_cbs)}</dd>
          </div>
          <div className="flex justify-between gap-3 py-0.5">
            <dt className="text-muted-foreground">IBS UF</dt>
            <dd className="font-mono tabular-nums text-foreground">{fmtMoney(d.valor_ibs_uf)}</dd>
          </div>
          <div className="flex justify-between gap-3 py-0.5">
            <dt className="text-muted-foreground">IBS Município</dt>
            <dd className="font-mono tabular-nums text-foreground">{fmtMoney(d.valor_ibs_municipio)}</dd>
          </div>
          <div className="flex justify-between gap-3 py-0.5">
            <dt className="text-muted-foreground">IBS total</dt>
            <dd className="font-mono font-semibold tabular-nums text-foreground">{fmtMoney(ibsTot)}</dd>
          </div>
          <div className="flex justify-between gap-3 sm:col-span-2 py-1 border-t border-border/40">
            <dt className="text-muted-foreground">Imposto seletivo (IS)</dt>
            <dd className="font-mono tabular-nums text-foreground">{fmtMoney(d.valor_is)}</dd>
          </div>
        </dl>
      )}
      {tagsComValoresZerados ? (
        <p className="text-sm rounded-lg border border-amber-200/80 bg-amber-50/90 text-amber-950 px-3 py-2">
          Tags CBS/IBS encontradas com valores zerados no XML.
        </p>
      ) : null}
      <div className="text-xs text-muted-foreground space-y-1.5 border-t border-border/40 pt-3">
        <p>
          Itens/documentos com tags CBS/IBS:{' '}
          <span className="font-semibold text-foreground tabular-nums">{d.itens_com_tags_ibscbs ?? 0}</span>
        </p>
        <p>
          Itens/documentos com valores CBS/IBS:{' '}
          <span className="font-semibold text-foreground tabular-nums">{d.itens_com_valores_ibscbs ?? 0}</span>
        </p>
        {(d.notas_com_ibscbstot ?? 0) > 0 ? (
          <p>
            Notas com IBSCBSTot: <span className="font-semibold text-foreground tabular-nums">{d.notas_com_ibscbstot}</span>
          </p>
        ) : null}
        {(d.cte_com_tags_ibscbs ?? 0) > 0 ? (
          <p>
            CT-es com tags CBS/IBS: <span className="font-semibold text-foreground tabular-nums">{d.cte_com_tags_ibscbs}</span>
          </p>
        ) : null}
      </div>
    </section>
  );
}

function severidadeBadgeClass(sev: string) {
  const s = (sev || '').toLowerCase();
  if (s === 'error' || s === 'critical' || s === 'critico') return 'erp-badge-danger';
  if (s === 'warning' || s === 'warn' || s === 'atencao') return 'erp-badge-warning';
  return 'erp-badge-info';
}

function severidadeLabel(sev: string) {
  const s = (sev || '').toLowerCase();
  if (s === 'error' || s === 'critical' || s === 'critico') return 'Crítico';
  if (s === 'warning' || s === 'warn' || s === 'atencao') return 'Atenção';
  return 'Info';
}

/** Card de leitura operacional (visão geral): valor em destaque, menos aspecto de “form”. */
function KpiCardHero({ titulo, valor, sub }: { titulo: string; valor: React.ReactNode; sub: string }) {
  return (
    <div className="rounded-2xl border border-border/50 bg-gradient-to-b from-card to-muted/15 p-6 md:p-7 shadow-sm flex flex-col gap-2 min-h-[132px] ring-1 ring-border/30">
      <h3 className="text-sm font-semibold text-foreground tracking-tight">{titulo}</h3>
      <p className="text-4xl font-bold tabular-nums text-foreground tracking-tight leading-none">{valor}</p>
      <p className="text-sm text-muted-foreground leading-snug mt-auto pt-1">{sub}</p>
    </div>
  );
}

function ChainMiniCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border/50 bg-muted/20 px-3 py-3 text-center">
      <div className="text-[11px] text-muted-foreground leading-tight">{label}</div>
      <div className="text-lg font-semibold tabular-nums text-foreground mt-1">{value}</div>
    </div>
  );
}

function AcumuloTable({ titulo, a }: { titulo: string; a: ApuracaoFiscalAcumulo | undefined }) {
  if (!a) {
    return (
      <div className="rounded-2xl border border-dashed border-border/70 bg-muted/10 p-8 text-center text-sm text-muted-foreground">
        {titulo}: sem dados nesta visão.
      </div>
    );
  }
  const isEntrada = titulo.toLowerCase().includes('entrada');
  const isSaida = titulo.toLowerCase().includes('saída') || titulo.toLowerCase().includes('saida');
  const sufixo = isEntrada ? 'entrada' : isSaida ? 'saída' : '';
  const rows: [string, number, 'int' | 'money'][] = [
    ['Notas fiscais', a.quantidade_notas, 'int'],
    ['Itens fiscais', a.quantidade_itens, 'int'],
    ['Valor dos documentos', a.valor_documentos, 'money'],
    ['Valor dos produtos', a.valor_produtos, 'money'],
    [`Base ICMS ${sufixo}`.trim(), a.base_icms, 'money'],
    [`ICMS ${sufixo}`.trim(), a.valor_icms, 'money'],
    [`Base IPI ${sufixo}`.trim(), a.base_ipi, 'money'],
    [`IPI ${sufixo}`.trim(), a.valor_ipi, 'money'],
    [`Base PIS ${sufixo}`.trim(), a.base_pis, 'money'],
    [`PIS ${sufixo}`.trim(), a.valor_pis, 'money'],
    [`Base COFINS ${sufixo}`.trim(), a.base_cofins, 'money'],
    [`COFINS ${sufixo}`.trim(), a.valor_cofins, 'money'],
  ];
  return (
    <div className="rounded-2xl border border-border/60 bg-card shadow-sm overflow-hidden flex flex-col">
      <div className="px-5 py-4 border-b border-border/60 bg-muted/25">
        <h3 className="text-base font-semibold text-foreground">{titulo}</h3>
      </div>
      <div className="overflow-auto max-h-[min(440px,55vh)]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-sm border-b border-border/80">
            <tr>
              <th className="text-left font-medium text-foreground/90 px-5 py-3">Indicador</th>
              <th className="text-right font-medium text-foreground/90 px-5 py-3 w-[140px]">Valor</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {rows.map(([k, v, kind]) => (
              <tr key={k} className="hover:bg-muted/15">
                <td className="text-muted-foreground px-5 py-2.5">{k}</td>
                <td className="text-right font-mono tabular-nums px-5 py-2.5 text-foreground">
                  {kind === 'int' ? v.toLocaleString('pt-BR') : fmtMoneyPlain(v)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SaldoGerencialTable({ saldo }: { saldo: Record<string, number> | undefined }) {
  if (!saldo || !Object.keys(saldo).length) return null;
  const labels: Record<string, string> = {
    valor_documentos: 'Valor total de documentos',
    valor_produtos: 'Valor total de produtos',
    base_icms: 'Base ICMS',
    valor_icms: 'Valor ICMS',
    base_ipi: 'Base IPI',
    valor_ipi: 'Valor IPI',
    base_pis: 'Base PIS',
    valor_pis: 'Valor PIS',
    base_cofins: 'Base COFINS',
    valor_cofins: 'Valor COFINS',
  };
  return (
    <div className="rounded-2xl border border-border/60 bg-card shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-border/60 bg-muted/25">
        <h3 className="text-base font-semibold text-foreground">Saldo gerencial (saídas − entradas)</h3>
        <p className="text-xs text-muted-foreground mt-1">Valores positivos indicam débito líquido.</p>
      </div>
      <div className="overflow-auto max-h-[min(360px,45vh)]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-sm border-b border-border/80">
            <tr>
              <th className="text-left font-medium px-5 py-3">Indicador</th>
              <th className="text-right font-medium px-5 py-3">Saldo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {Object.entries(saldo).map(([k, v]) => (
              <tr key={k} className="hover:bg-muted/15">
                <td className="text-muted-foreground px-5 py-2.5">{labels[k] ?? k}</td>
                <td className="text-right font-mono tabular-nums px-5 py-2.5">{fmtMoneyPlain(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AgrupTable({
  titulo,
  rows,
}: {
  titulo: string;
  rows: Array<{ chave: string } & ApuracaoFiscalAcumulo> | undefined;
}) {
  const empty = !rows?.length;
  return (
    <div className="rounded-2xl border border-border/50 bg-card shadow-sm overflow-hidden flex flex-col ring-1 ring-border/15">
      <div className="px-5 py-4 border-b border-border/60 bg-muted/15">
        <h4 className="text-base font-semibold text-foreground">{titulo}</h4>
      </div>
      {empty ? (
        <p className="text-sm text-muted-foreground px-5 py-12 text-center">Nenhum agrupamento para estes filtros.</p>
      ) : (
        <div className="overflow-auto max-h-[min(520px,60vh)]">
          <table className="w-full text-sm min-w-[760px]">
            <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-sm border-b border-border/80">
              <tr>
                <th className="text-left font-semibold text-foreground/90 px-5 py-3">Código</th>
                <th className="text-left font-semibold text-foreground/90 px-5 py-3 min-w-[180px]">Nome / descrição</th>
                <th className="text-right font-semibold text-foreground/90 px-5 py-3">Itens</th>
                <th className="text-right font-semibold text-foreground/90 px-5 py-3">Valor produtos</th>
                <th className="text-right font-semibold text-foreground/90 px-5 py-3">Valor ICMS</th>
                <th className="text-right font-semibold text-foreground/90 px-5 py-3">Valor PIS</th>
                <th className="text-right font-semibold text-foreground/90 px-5 py-3">Valor COFINS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {rows!.slice(0, 200).map((r) => (
                <tr key={r.chave} className="hover:bg-muted/15">
                  <td className="font-mono text-xs px-5 py-2.5 align-top max-w-[160px] truncate" title={r.chave}>
                    {r.chave}
                  </td>
                  <td className="text-muted-foreground px-5 py-2.5 align-top text-xs max-w-[300px] break-words" title={r.chave}>
                    {r.chave}
                  </td>
                  <td className="text-right tabular-nums px-5 py-2.5 align-top">{r.quantidade_itens}</td>
                  <td className="text-right font-mono tabular-nums px-5 py-2.5 align-top">{fmtMoneyPlain(r.valor_produtos)}</td>
                  <td className="text-right font-mono tabular-nums px-5 py-2.5 align-top">{fmtMoneyPlain(r.valor_icms)}</td>
                  <td className="text-right font-mono tabular-nums px-5 py-2.5 align-top">{fmtMoneyPlain(r.valor_pis)}</td>
                  <td className="text-right font-mono tabular-nums px-5 py-2.5 align-top">{fmtMoneyPlain(r.valor_cofins)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function LadoFiscalReadonlyCard({
  titulo,
  rows,
  footer,
}: {
  titulo: string;
  rows: { label: string; value: React.ReactNode }[];
  footer?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border/50 bg-gradient-to-b from-card to-muted/10 p-6 md:p-7 shadow-sm ring-1 ring-border/15 flex flex-col gap-4">
      <h3 className="text-base font-semibold text-foreground border-b border-border/50 pb-3">{titulo}</h3>
      <dl className="space-y-3.5 flex-1">
        {rows.map((row) => (
          <div key={row.label} className="flex justify-between gap-4 items-baseline">
            <dt className="text-sm text-muted-foreground shrink">{row.label}</dt>
            <dd className="text-sm font-mono font-semibold tabular-nums text-foreground text-right">{row.value}</dd>
          </div>
        ))}
      </dl>
      {footer ? <div className="text-xs text-muted-foreground border-t border-border/40 pt-3 mt-auto">{footer}</div> : null}
    </div>
  );
}

function icmsIpiRows(a?: ApuracaoFiscalAcumulo) {
  return [
    { label: 'Base ICMS', value: fmtMoney(a?.base_icms) },
    { label: 'ICMS', value: fmtMoney(a?.valor_icms) },
    { label: 'Base IPI', value: fmtMoney(a?.base_ipi) },
    { label: 'IPI', value: fmtMoney(a?.valor_ipi) },
    { label: 'Valor dos documentos', value: fmtMoney(a?.valor_documentos) },
    { label: 'Valor dos produtos', value: fmtMoney(a?.valor_produtos) },
  ];
}

function pisCofinsRows(a?: ApuracaoFiscalAcumulo) {
  return [
    { label: 'Base PIS', value: fmtMoney(a?.base_pis) },
    { label: 'PIS', value: fmtMoney(a?.valor_pis) },
    { label: 'Base COFINS', value: fmtMoney(a?.base_cofins) },
    { label: 'COFINS', value: fmtMoney(a?.valor_cofins) },
  ];
}

function saldoSaidaMenosEntrada(
  e: ApuracaoFiscalAcumulo | undefined,
  s: ApuracaoFiscalAcumulo | undefined,
  pick: keyof ApuracaoFiscalAcumulo,
) {
  const ve = e?.[pick];
  const vs = s?.[pick];
  if (typeof ve !== 'number' && typeof vs !== 'number') return undefined;
  return (typeof vs === 'number' ? vs : 0) - (typeof ve === 'number' ? ve : 0);
}

function DiagnosticoDasFontesPainel({
  filtros,
  fontes,
  diag,
}: {
  filtros?: ApuracaoFiscalPayload['filtros'] | null;
  fontes?: ApuracaoFiscalFontes;
  diag?: ApuracaoDiagnosticoFontes;
}) {
  if (!diag) return null;
  const n = (v: unknown) => {
    const x = Number(v);
    return Number.isFinite(x) ? x : 0;
  };
  return (
    <details className="rounded-2xl border border-border/60 bg-card shadow-sm overflow-hidden">
      <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30 transition-colors">
        Diagnóstico das fontes
      </summary>
      <div className="px-5 pb-6 space-y-6 border-t border-border/50 pt-5">
        {filtros ? (
          <p className="text-xs text-muted-foreground">
            Datas enviadas nesta resposta:{' '}
            <span className="font-mono text-foreground">
              {filtros.data_inicio?.slice(0, 10)} → {filtros.data_fim?.slice(0, 10)}
            </span>
          </p>
        ) : null}
        {fontes ? (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Candidatas (após filtros)</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              <ChainMiniCard label="Base NF-e saída importada" value={n(fontes.saidas_historicas_candidatas)} />
              <ChainMiniCard label="Base NF-e entrada importada" value={n(fontes.entradas_historicas_candidatas)} />
              <ChainMiniCard label="Saída operacional" value={n(fontes.saidas_operacionais_candidatas)} />
              <ChainMiniCard label="Entrada operacional" value={n(fontes.entradas_operacionais_candidatas)} />
              <ChainMiniCard label="Saída hist. período (sem empresa)" value={n(fontes.saidas_historicas_periodo_sem_filtro_empresa)} />
              <ChainMiniCard label="Entrada hist. período (sem empresa)" value={n(fontes.entradas_historicas_periodo_sem_filtro_empresa)} />
            </div>
          </div>
        ) : null}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">NF saída histórica — encadeamento</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            <ChainMiniCard label="No banco" value={n(diag.saidas_historicas_total_banco)} />
            <ChainMiniCard label="No período" value={n(diag.saidas_historicas_no_periodo)} />
            <ChainMiniCard label="Após empresa" value={n(diag.saidas_historicas_apos_empresa)} />
            <ChainMiniCard label="Após status" value={n(diag.saidas_historicas_apos_status)} />
            <ChainMiniCard label="Após canceladas" value={n(diag.saidas_historicas_apos_canceladas)} />
            <ChainMiniCard label="Incluídas" value={n(diag.saidas_historicas_incluidas)} />
          </div>
        </div>
        {(diag.campo_data_usado || diag.campo_valor_usado || diag.campo_status_usado || diag.campo_empresa_usado) ? (
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            {diag.campo_data_usado ? (
              <span className="rounded-md bg-muted/50 px-2 py-1">Data: {String(diag.campo_data_usado)}</span>
            ) : null}
            {diag.campo_valor_usado ? (
              <span className="rounded-md bg-muted/50 px-2 py-1">Valor: {String(diag.campo_valor_usado)}</span>
            ) : null}
            {diag.campo_status_usado ? (
              <span className="rounded-md bg-muted/50 px-2 py-1">Status: {String(diag.campo_status_usado)}</span>
            ) : null}
            {diag.campo_empresa_usado ? (
              <span className="rounded-md bg-muted/50 px-2 py-1">Empresa: {String(diag.campo_empresa_usado)}</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </details>
  );
}

function ibsTotalDet(d?: ApuracaoReformaDetalhe) {
  if (!d) return 0;
  return d.valor_ibs_total ?? (d.valor_ibs_uf ?? 0) + (d.valor_ibs_municipio ?? 0);
}

function ReformaTabelaComparativa({ r }: { r: ApuracaoReformaTributaria | undefined }) {
  const p = r?.por_documento;
  const linhas: { origem: string; d?: ApuracaoReformaDetalhe }[] = [
    { origem: 'Entrada', d: p?.entrada },
    { origem: 'Saída', d: p?.saida },
    { origem: 'CT-e', d: p?.cte },
  ];
  const baseCons = r?.base_cbs ?? r?.base_ibs;
  const ibsTotCons = r?.valor_ibs_total ?? (r?.valor_ibs_uf ?? 0) + (r?.valor_ibs_municipio ?? 0);

  return (
    <div className="rounded-2xl border border-border/60 bg-card shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-border/60 bg-muted/20">
        <h2 className="text-base font-semibold text-foreground">Conferência por origem</h2>
        <p className="text-xs text-muted-foreground mt-1">Comparativo entre entrada, saída e CT-e no mesmo período.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-muted/40 border-b border-border/60">
            <tr>
              <th className="text-left font-semibold text-foreground px-4 py-3">Origem</th>
              <th className="text-right font-semibold text-foreground px-4 py-3 whitespace-nowrap">Base CBS/IBS</th>
              <th className="text-right font-semibold text-foreground px-4 py-3 whitespace-nowrap">CBS</th>
              <th className="text-right font-semibold text-foreground px-4 py-3 whitespace-nowrap">IBS UF</th>
              <th className="text-right font-semibold text-foreground px-4 py-3 whitespace-nowrap">IBS Município</th>
              <th className="text-right font-semibold text-foreground px-4 py-3 whitespace-nowrap">IBS total</th>
              <th className="text-right font-semibold text-foreground px-4 py-3 whitespace-nowrap">IS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {linhas.map(({ origem, d }) => (
              <tr key={origem} className="hover:bg-muted/15">
                <td className="px-4 py-2.5 font-medium text-foreground">{origem}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-foreground">{baseCbsIbsDisplay(d)}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">{fmtMoney(d?.valor_cbs)}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">{fmtMoney(d?.valor_ibs_uf)}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">{fmtMoney(d?.valor_ibs_municipio)}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums font-medium">{fmtMoney(ibsTotalDet(d))}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums">{fmtMoney(d?.valor_is)}</td>
              </tr>
            ))}
            <tr className="bg-muted/25 font-semibold">
              <td className="px-4 py-3 text-foreground">Total</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{fmtMoney(baseCons)}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{fmtMoney(r?.valor_cbs)}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{fmtMoney(r?.valor_ibs_uf)}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{fmtMoney(r?.valor_ibs_municipio)}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{fmtMoney(ibsTotCons)}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-foreground">{fmtMoney(r?.valor_is)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DiagnosticoReformaTecnicoAccordion({
  dr,
  r,
  fontes,
}: {
  dr?: ApuracaoDiagnosticoReforma;
  r?: ApuracaoReformaTributaria;
  fontes?: ApuracaoFiscalFontes;
}) {
  const ctesEscaneados = fontes?.ctes_historicos_escaneados_reforma;
  return (
    <details className="rounded-2xl border border-border/60 bg-muted/10 overflow-hidden">
      <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">
        ▸ Diagnóstico técnico da Reforma
      </summary>
      <div className="px-5 pb-6 space-y-5 border-t border-border/50 pt-4 text-sm">
        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">candidatas_entrada_historica</dt>
            <dd className="font-mono tabular-nums text-foreground">{dr?.candidatas_entrada_historica ?? '—'}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">candidatas_saida_historica</dt>
            <dd className="font-mono tabular-nums text-foreground">{dr?.candidatas_saida_historica ?? '—'}</dd>
          </div>
          <div className="flex flex-col gap-0.5 sm:col-span-2">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">CT-es escaneados</dt>
            <dd className="font-mono tabular-nums text-foreground">{ctesEscaneados ?? '—'}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Itens com tags CBS/IBS (consolidado)</dt>
            <dd className="font-mono tabular-nums text-foreground">{r?.itens_com_tags_ibscbs ?? '—'}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Itens com valores CBS/IBS (consolidado)</dt>
            <dd className="font-mono tabular-nums text-foreground">{r?.itens_com_valores_ibscbs ?? '—'}</dd>
          </div>
          <div className="flex flex-col gap-0.5 sm:col-span-2">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Notas com IBSCBSTot</dt>
            <dd className="font-mono tabular-nums text-foreground">{r?.notas_com_ibscbstot ?? '—'}</dd>
          </div>
          <div className="flex flex-col gap-0.5 sm:col-span-2">
            <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Leitura usada</dt>
            <dd className="text-muted-foreground text-xs leading-relaxed">
              Valores consolidados vêm de <span className="font-mono text-foreground">reforma_tributaria</span> na resposta da
              apuração (tags/valores mapeados no XML conforme versão da API).
            </dd>
          </div>
        </dl>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">diagnostico_reforma (JSON)</p>
          <pre className="text-xs font-mono overflow-auto max-h-72 p-4 rounded-xl bg-muted/50 border border-border/50 text-foreground/90">
            {JSON.stringify(dr ?? {}, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  );
}

function ReformaTributariaPainel({
  r,
  cardsKpi,
  fonte,
  tipo,
  fontes,
  temNotasNoPeriodo,
  diagnosticoReforma,
}: {
  r: ApuracaoReformaTributaria | undefined;
  cardsKpi?: Record<string, number>;
  fonte: string;
  tipo: string;
  fontes?: ApuracaoFiscalFontes;
  temNotasNoPeriodo: boolean;
  diagnosticoReforma?: ApuracaoDiagnosticoReforma;
}) {
  const porDoc = r?.por_documento;
  const valorCbs = r?.valor_cbs ?? 0;
  const valorIbsUf = r?.valor_ibs_uf ?? 0;
  const valorIbsMun = r?.valor_ibs_municipio ?? 0;
  const valorIbsTotal = r?.valor_ibs_total ?? valorIbsUf + valorIbsMun;
  const valorIs = r?.valor_is ?? 0;
  const semValores = valorCbs === 0 && valorIbsTotal === 0 && valorIs === 0;
  const itTags = r?.itens_com_tags_ibscbs ?? 0;
  const itVals = r?.itens_com_valores_ibscbs ?? 0;
  const notasTot = r?.notas_com_ibscbstot ?? 0;
  const cteTags = r?.cte_com_tags_ibscbs ?? 0;
  const temTagsIbscbs = itTags > 0 || notasTot > 0 || cteTags > 0;

  const numK = (v: unknown) => {
    const x = Number(v);
    return Number.isFinite(x) ? x : 0;
  };
  const kpiCbs = numK(cardsKpi?.cbs);
  const kpiIbs = numK(cardsKpi?.ibs);
  const kpiIs = numK(cardsKpi?.is);
  const kpisReformaZerados = kpiCbs === 0 && kpiIbs === 0 && kpiIs === 0;
  const histCandidatas =
    (fontes?.saidas_historicas_candidatas ?? 0) + (fontes?.entradas_historicas_candidatas ?? 0);
  const histNoPeriodo =
    (fontes?.saidas_historicas_periodo_sem_filtro_empresa ?? 0) +
    (fontes?.entradas_historicas_periodo_sem_filtro_empresa ?? 0);

  const baseConsolidada = r?.base_cbs ?? r?.base_ibs;

  return (
    <div className="space-y-8">
      <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
        Painel de conferência fiscal da Reforma Tributária (CBS/IBS/IS). Os valores respeitam o período e os filtros da
        apuração (empresa, tipo, fonte, CFOP/NCM). Amplie as datas se notas importadas ficarem fora do intervalo.
      </p>
      {kpisReformaZerados && fonte === 'OPERACIONAIS' ? (
        <div className="rounded-xl border border-violet-200/90 bg-violet-50/90 px-5 py-4 text-sm text-violet-950">
          <p className="font-medium">Fonte “Operacionais” não inclui NF-e importada por XML.</p>
          <p className="mt-2 text-violet-900/90">
            CBS/IBS/IS da Reforma são somados a partir de NF-e <strong>histórica</strong> (importação XML). Use a fonte
            “Históricos” ou “Todos” para ver esses valores.
          </p>
        </div>
      ) : null}
      {kpisReformaZerados && fonte !== 'OPERACIONAIS' && tipo !== 'AMBOS' ? (
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/90 px-5 py-4 text-sm text-slate-900">
          <p className="font-medium">Filtro “Tipo” limita o lado da NF-e.</p>
          <p className="mt-2 text-slate-800/90">
            Com <strong>{tipo === 'SAIDA' ? 'Saída' : 'Entrada'}</strong>, apenas notas desse lado entram na apuração. Se
            as tags CBS/IBS estiverem só em compras ou só em vendas, escolha <strong>Ambos</strong> ou o lado correto.
          </p>
        </div>
      ) : null}
      {kpisReformaZerados &&
      fonte !== 'OPERACIONAIS' &&
      histCandidatas === 0 &&
      histNoPeriodo > 0 &&
      temNotasNoPeriodo ? (
        <div className="rounded-xl border border-orange-200/90 bg-orange-50/90 px-5 py-4 text-sm text-orange-950">
          <p className="font-medium">Há NF histórica no período, mas nenhuma candidata com os filtros atuais.</p>
          <p className="mt-2 text-orange-900/90">
            Confira <strong>empresa</strong>, <strong>CFOP/NCM</strong> e <strong>tipo</strong>. Na aba Informações
            técnicas, as contagens de fontes ajudam a ver onde as notas param no filtro.
          </p>
        </div>
      ) : null}
      {semValores && temTagsIbscbs && (
        <div className="rounded-xl border border-sky-200/90 bg-sky-50/90 px-5 py-4 text-sm text-sky-950">
          <p className="font-medium">Tags CBS/IBS encontradas com valores zerados no XML.</p>
          {cteTags > 0 && valorCbs + valorIbsTotal === 0 ? (
            <p className="mt-2 text-sky-900/90">
              Há CT-e com tags no período; confira o bloco CT-e abaixo ou amplie o intervalo de datas.
            </p>
          ) : null}
        </div>
      )}
      {semValores && !temTagsIbscbs && (
        <div className="rounded-xl border border-amber-200/90 bg-amber-50/90 px-5 py-4 text-sm text-amber-950">
          <p className="font-medium">Estrutura preparada para Reforma Tributária. Nenhum valor CBS/IBS/IS encontrado no período.</p>
          {!temNotasNoPeriodo ? (
            <p className="mt-2 text-amber-900/90">Os tributos dependem de tags mapeadas no XML ou cadastros futuros.</p>
          ) : null}
        </div>
      )}

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground tracking-tight">Totais consolidados</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 md:gap-5">
          <KpiCardHero titulo="CBS consolidado" valor={fmtMoney(r?.valor_cbs)} sub="Somatório de entrada, saída e CT-e" />
          <KpiCardHero titulo="IBS consolidado" valor={fmtMoney(valorIbsTotal)} sub="UF + Município no período filtrado" />
          <KpiCardHero titulo="IS consolidado" valor={fmtMoney(r?.valor_is)} sub="Imposto seletivo somado na apuração" />
          <KpiCardHero titulo="Base CBS/IBS consolidada" valor={fmtMoney(baseConsolidada)} sub="Base agregada conforme retorno da API" />
        </div>
      </section>

      <ReformaTabelaComparativa r={r} />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground tracking-tight">Detalhe por origem</h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <ReformaBlocoOrigem titulo="Reforma — Entrada" subtitulo="NF-e e documentos no lado entrada" d={porDoc?.entrada} />
          <ReformaBlocoOrigem titulo="Reforma — Saída" subtitulo="NF-e e documentos no lado saída" d={porDoc?.saida} />
          <ReformaBlocoOrigem titulo="Reforma — CT-e" subtitulo="Valores somados ao consolidado acima" d={porDoc?.cte} />
        </div>
      </section>

      <DiagnosticoReformaTecnicoAccordion dr={diagnosticoReforma} r={r} fontes={fontes} />
    </div>
  );
}

function EfdIcmsIpiPainel({ efd, totalNotas }: { efd: ApuracaoEfdIcmsIpi | undefined; totalNotas: number }) {
  const ind = efd?.indicadores ?? {};
  const efdIcmsGrid = [
    { cod: 'C100', titulo: 'Documentos fiscais', valor: ind.notas_mapeaveis_c100 ?? 0, sub: 'Documentos fiscais mapeáveis' },
    { cod: 'C170', titulo: 'Itens de documento', valor: ind.itens_mapeaveis_c170 ?? 0, sub: 'Itens mapeáveis para C170' },
    { cod: 'C190', titulo: 'Agrupamentos CST/CFOP/alíquota', valor: ind.agrupamentos_possiveis_c190 ?? 0, sub: 'Chaves C190 possíveis na base' },
    { cod: '0150', titulo: 'Participantes', valor: ind.itens_cadastro_participante_0150_pendentes ?? 0, sub: 'Pendências cadastro participante' },
    { cod: '0190', titulo: 'Unidades', valor: '—', sub: 'Indicador consolidado em evolução na API' },
    { cod: '0200', titulo: 'Produtos', valor: ind.produtos_cadastro_0200_pendentes ?? 0, sub: 'Pendências cadastro produto' },
  ];
  const faltantes = ind.notas_com_campos_faltantes_c100 ?? 0;

  return (
    <div className="space-y-8">
      {totalNotas === 0 ? (
        <p className="text-sm text-muted-foreground border border-dashed border-border/80 rounded-2xl px-6 py-10 text-center bg-muted/10">
          Nenhuma base EFD ICMS/IPI encontrada para o período selecionado.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {efdIcmsGrid.map((c) => (
            <div key={c.cod} className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{c.cod}</div>
              <div className="text-xs text-foreground/80 mt-0.5">{c.titulo}</div>
              <div className="text-3xl font-bold tabular-nums mt-3 text-foreground">{c.valor}</div>
              <p className="text-xs text-muted-foreground mt-2 leading-snug">{c.sub}</p>
            </div>
          ))}
        </div>
      )}

      {totalNotas > 0 && faltantes > 0 ? (
        <p className="text-sm text-amber-900 bg-amber-50/90 border border-amber-200 rounded-xl px-4 py-3">
          <span className="font-medium">C100 com campos faltantes (E100/E110 futuro):</span> {faltantes}
        </p>
      ) : null}

      {efd?.observacao ? <p className="text-sm text-muted-foreground leading-relaxed">{efd.observacao}</p> : null}

      {efd?.alertas?.length ? (
        <details className="rounded-xl border border-border/60 bg-muted/10">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-foreground">Alertas de completude / campos</summary>
          <ul className="list-disc pl-8 pr-4 pb-4 text-sm text-muted-foreground space-y-1">
            {efd.alertas.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {efd?.registros_planejados && Object.keys(efd.registros_planejados).length > 0 ? (
        <details className="rounded-xl border border-border/60 bg-card">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-foreground">Registros SPED planejados (referência)</summary>
          <div className="px-4 pb-4 space-y-3 text-sm">
            {Object.entries(efd.registros_planejados).map(([bloco, regs]) => (
              <div key={bloco}>
                <span className="text-xs font-semibold uppercase text-muted-foreground">{bloco}</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {(regs || []).map((reg) => (
                    <span key={reg} className="erp-badge-info text-xs py-0.5 px-2">
                      {reg}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function EfdContribuicoesPainel({ efd, totalNotas }: { efd: ApuracaoEfdContribuicoes | undefined; totalNotas: number }) {
  const ind = efd?.indicadores ?? {};
  const alertasN = efd?.alertas?.length ?? 0;
  const efdContribGrid: { titulo: string; valor: number | string; sub: string }[] = [
    { titulo: 'Documentos com PIS/COFINS', valor: ind.notas_com_totais_pis_cofins_documento ?? 0, sub: 'NF com totais de documento' },
    { titulo: 'Itens com CST PIS', valor: ind.itens_com_cst_pis ?? 0, sub: 'CST PIS informado no item' },
    { titulo: 'Itens com CST COFINS', valor: ind.itens_com_cst_cofins ?? 0, sub: 'CST COFINS informado no item' },
    { titulo: 'Bases PIS preenchidas', valor: ind.itens_com_base_pis ?? 0, sub: 'Itens com base PIS' },
    { titulo: 'Bases COFINS preenchidas', valor: ind.itens_com_base_cofins ?? 0, sub: 'Itens com base COFINS' },
    { titulo: 'Possíveis créditos', valor: ind.creditos_entrada_possiveis ?? 0, sub: 'Itens de entrada' },
    { titulo: 'Possíveis débitos', valor: ind.debitos_saida_possiveis ?? 0, sub: 'Itens de saída' },
    { titulo: 'Campos faltantes (alertas)', valor: alertasN, sub: 'Mensagens técnicas da base Contribuições' },
  ];

  return (
    <div className="space-y-8">
      {totalNotas === 0 ? (
        <p className="text-sm text-muted-foreground border border-dashed border-border/80 rounded-2xl px-6 py-10 text-center bg-muted/10">
          Nenhuma base EFD Contribuições encontrada para o período selecionado.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {efdContribGrid.map((c) => (
            <div key={c.titulo} className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-foreground leading-snug">{c.titulo}</h3>
              <div className="text-3xl font-bold tabular-nums mt-3 text-foreground">{c.valor}</div>
              <p className="text-xs text-muted-foreground mt-2 leading-snug">{c.sub}</p>
            </div>
          ))}
        </div>
      )}

      {efd?.observacao ? <p className="text-sm text-muted-foreground leading-relaxed">{efd.observacao}</p> : null}

      {efd?.alertas?.length ? (
        <details className="rounded-xl border border-border/60 bg-muted/10">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-foreground">Detalhe dos alertas técnicos</summary>
          <ul className="list-disc pl-8 pr-4 pb-4 text-sm text-muted-foreground space-y-1">
            {efd.alertas.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {efd?.registros_planejados && Object.keys(efd.registros_planejados).length > 0 ? (
        <details className="rounded-xl border border-border/60 bg-card">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-foreground">Registros SPED planejados (referência)</summary>
          <div className="px-4 pb-4 space-y-3 text-sm">
            {Object.entries(efd.registros_planejados).map(([bloco, regs]) => (
              <div key={bloco}>
                <span className="text-xs font-semibold uppercase text-muted-foreground">{bloco}</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {(regs || []).map((reg) => (
                    <span key={reg} className="erp-badge-info text-xs py-0.5 px-2">
                      {reg}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function PainelInformacoesTecnicas({ data }: { data: ApuracaoFiscalPayload }) {
  const d = data.diagnostico;
  const temDiag = d && Object.keys(d).length > 0;
  return (
    <div className="space-y-5 md:space-y-6">
      <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
        <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">
          Filtros recebidos pela API
        </summary>
        <pre className="text-xs font-mono overflow-auto max-h-[320px] p-5 m-0 border-t border-border/50 bg-muted/20 text-foreground/90">
          {JSON.stringify(data.filtros, null, 2)}
        </pre>
      </details>

      <div className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
        <div className="px-5 py-4 border-b border-border/60 bg-muted/15">
          <h3 className="text-sm font-semibold text-foreground">Diagnóstico de fontes</h3>
          <p className="text-xs text-muted-foreground mt-1">Candidatas, encadeamento e campos usados na consulta.</p>
        </div>
        <div className="p-4 md:p-5">
          {data.diagnostico_fontes ? (
            <DiagnosticoDasFontesPainel filtros={data.filtros} fontes={data.fontes} diag={data.diagnostico_fontes} />
          ) : (
            <p className="text-sm text-muted-foreground">Sem diagnóstico de fontes nesta resposta.</p>
          )}
        </div>
      </div>

      <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
        <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">
          Diagnóstico da Reforma
        </summary>
        <pre className="text-xs font-mono overflow-auto max-h-[360px] p-5 m-0 border-t border-border/50 bg-muted/20 text-foreground/90">
          {JSON.stringify(data.diagnostico_reforma ?? {}, null, 2)}
        </pre>
      </details>

      {!temDiag ? (
        <p className="text-sm text-muted-foreground border border-dashed border-border/70 rounded-xl px-4 py-3 bg-muted/10">
          Sem bloco de diagnóstico amigável nesta versão da API.
        </p>
      ) : null}
      {temDiag ? (
        <>
          <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
            <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">Models utilizados</summary>
            <div className="px-5 pb-5 pt-0 border-t border-border/50">
              {d.models_utilizados?.length ? (
                <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1 pt-3">
                  {d.models_utilizados.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground pt-3">—</p>
              )}
            </div>
          </details>
          <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
            <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">Campos fiscais XML</summary>
            <div className="px-5 pb-5 pt-0 border-t border-border/50">
              {d.campos_fiscais_xml?.length ? (
                <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1 pt-3">
                  {d.campos_fiscais_xml.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground pt-3">—</p>
              )}
            </div>
          </details>
          <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
            <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">Campos ausentes SPED / Reforma</summary>
            <div className="px-5 pb-5 pt-0 border-t border-border/50">
              {d.campos_ausentes_sped_reforma?.length ? (
                <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1 pt-3">
                  {d.campos_ausentes_sped_reforma.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground pt-3">—</p>
              )}
            </div>
          </details>
          {d.impacto ? (
            <div className="rounded-2xl border border-border/60 bg-muted/15 px-5 py-4 text-sm">
              <span className="font-semibold text-foreground">Impacto: </span>
              <span className="text-muted-foreground">{d.impacto}</span>
            </div>
          ) : null}
        </>
      ) : null}

      <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
        <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">
          Diagnóstico bruto de fontes (JSON)
        </summary>
        <pre className="text-xs font-mono overflow-auto max-h-[320px] p-5 m-0 border-t border-border/50 bg-muted/20 text-foreground/90">
          {JSON.stringify(data.diagnostico_fontes ?? {}, null, 2)}
        </pre>
      </details>

      <details className="rounded-2xl border border-border/60 bg-card overflow-hidden shadow-sm ring-1 ring-border/15">
        <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/30">Payload técnico (resposta)</summary>
        <pre className="text-xs font-mono overflow-auto max-h-[min(560px,70vh)] p-5 m-0 border-t border-border/50 bg-muted/20 text-foreground/90">
          {JSON.stringify(data, null, 2)}
        </pre>
      </details>

      <p className="text-xs text-muted-foreground px-1">
        API {data.meta?.versao_api_apuracao ?? '—'} · {data.meta?.pre_validacao ? 'Pré-validação' : '—'} ·{' '}
        {data.meta?.calculo === 'on_demand' ? 'Cálculo on-demand' : data.meta?.calculo ?? '—'}
      </p>
    </div>
  );
}

/** Garante que o eco `filtros` da API bate com o que o cliente enviou (evita aceitar default mês atual do backend). */
function filtrosEchoConfere(
  enviado: Record<string, string | number | boolean>,
  payload: ApuracaoFiscalPayload,
): boolean {
  return (
    isoDate10(enviado.data_inicio) === isoDate10(payload.filtros?.data_inicio) &&
    isoDate10(enviado.data_fim) === isoDate10(payload.filtros?.data_fim)
  );
}

function isApuracaoAbortError(e: unknown): boolean {
  if (!e || typeof e !== 'object') return false;
  const o = e as { code?: string; name?: string; message?: string };
  return o.code === 'ERR_CANCELED' || o.name === 'CanceledError' || o.message === 'canceled';
}

const ApuracaoFiscalPage = () => {
  const today = useMemo(() => new Date(), []);
  const anoCorrente = today.getFullYear();
  const mesCorrente = today.getMonth() + 1;
  const trimCorrente = Math.ceil(mesCorrente / 3);
  const semCorrente = mesCorrente <= 6 ? 1 : 2;
  const periodoMensalCorrente = useMemo(
    () => calcularPeriodoMensal(anoCorrente, mesCorrente),
    [anoCorrente, mesCorrente],
  );

  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [empresaId, setEmpresaId] = useState<string>('');
  const [periodoTipo, setPeriodoTipo] = useState<PeriodoTipoApuracao>('MENSAL');
  const [periodoMes, setPeriodoMes] = useState(mesCorrente);
  const [periodoAno, setPeriodoAno] = useState(anoCorrente);
  const [periodoTrimestre, setPeriodoTrimestre] = useState(trimCorrente);
  const [periodoSemestre, setPeriodoSemestre] = useState(semCorrente);
  const [dataInicio, setDataInicio] = useState(periodoMensalCorrente.data_inicio);
  const [dataFim, setDataFim] = useState(periodoMensalCorrente.data_fim);
  /** Em modo personalizado, atualizado no `onChange` antes do próximo render. */
  const dataInicioLiveRef = useRef(dataInicio);
  const dataFimLiveRef = useRef(dataFim);
  const [tipo, setTipo] = useState('AMBOS');
  const [fonte, setFonte] = useState<'TODOS' | 'OPERACIONAIS' | 'HISTORICOS'>('TODOS');
  const [status, setStatus] = useState('');
  const [cfop, setCfop] = useState('');
  const [ncm, setNcm] = useState('');
  const [modelo, setModelo] = useState('');
  const [incluirCanceladas, setIncluirCanceladas] = useState(false);
  const [tab, setTab] = useState<TabId>('resumo');
  const [data, setData] = useState<ApuracaoFiscalPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    empresasService.getAll().then(setEmpresas).catch(() => setEmpresas([]));
  }, []);

  /** Mantém `data_inicio`/`data_fim` alinhados à competência (exceto personalizado). Drill-down futuro pode reutilizar o mesmo objeto. */
  const periodoUiAtual = useMemo(
    (): PeriodoApuracaoUi => ({
      tipo: periodoTipo,
      mes: periodoMes,
      ano: periodoAno,
      trimestre: periodoTrimestre,
      semestre: periodoSemestre,
      data_inicio: dataInicio,
      data_fim: dataFim,
    }),
    [periodoTipo, periodoMes, periodoAno, periodoTrimestre, periodoSemestre, dataInicio, dataFim],
  );

  useEffect(() => {
    if (periodoTipo === 'PERSONALIZADO') return;
    const ui: PeriodoApuracaoUi = {
      tipo: periodoTipo,
      mes: periodoMes,
      ano: periodoAno,
      trimestre: periodoTrimestre,
      semestre: periodoSemestre,
      data_inicio: '',
      data_fim: '',
    };
    const { data_inicio, data_fim } = resolvePeriodoParaDatas(ui);
    dataInicioLiveRef.current = data_inicio;
    dataFimLiveRef.current = data_fim;
    setDataInicio(data_inicio);
    setDataFim(data_fim);
  }, [periodoTipo, periodoMes, periodoAno, periodoTrimestre, periodoSemestre]);

  const buildParams = useCallback(() => {
    const ui: PeriodoApuracaoUi = {
      tipo: periodoTipo,
      mes: periodoMes,
      ano: periodoAno,
      trimestre: periodoTrimestre,
      semestre: periodoSemestre,
      data_inicio: dataInicio,
      data_fim: dataFim,
    };
    let di: string;
    let df: string;
    if (periodoTipo === 'PERSONALIZADO') {
      di = String(dataInicioLiveRef.current ?? dataInicio ?? '').trim();
      df = String(dataFimLiveRef.current ?? dataFim ?? '').trim();
    } else {
      const r = resolvePeriodoParaDatas(ui);
      di = r.data_inicio;
      df = r.data_fim;
    }
    const p: Record<string, string | number | boolean> = {
      data_inicio: di,
      data_fim: df,
      tipo,
      fonte,
      incluir_canceladas: incluirCanceladas,
      ...montarExtrasPeriodoQuery(ui),
    };
    if (empresaId) p.empresa_id = Number(empresaId);
    if (status.trim()) p.status = status.trim();
    if (cfop.trim()) p.cfop = cfop.trim();
    if (ncm.trim()) p.ncm = ncm.trim();
    if (modelo.trim()) p.modelo_documento = modelo.trim();
    return p;
  }, [
    periodoTipo,
    periodoMes,
    periodoAno,
    periodoTrimestre,
    periodoSemestre,
    dataInicio,
    dataFim,
    tipo,
    fonte,
    incluirCanceladas,
    empresaId,
    status,
    cfop,
    ncm,
    modelo,
  ]);

  /** Qualquer mudança de filtro dispara nova apuração (debounce). Evita ficar zerado ao mudar só as datas sem clicar em Apurar. */
  const apuracaoQueryKey = useMemo(
    () =>
      [
        periodoTipo,
        String(periodoMes),
        String(periodoAno),
        String(periodoTrimestre),
        String(periodoSemestre),
        dataInicio,
        dataFim,
        tipo,
        fonte,
        String(incluirCanceladas),
        empresaId,
        status,
        cfop,
        ncm,
        modelo,
      ].join('|'),
    [
      periodoTipo,
      periodoMes,
      periodoAno,
      periodoTrimestre,
      periodoSemestre,
      dataInicio,
      dataFim,
      tipo,
      fonte,
      incluirCanceladas,
      empresaId,
      status,
      cfop,
      ncm,
      modelo,
    ],
  );

  const rotuloPeriodoSelecionado = useMemo(
    () => formatarRotuloPeriodoSelecionado(periodoUiAtual),
    [periodoUiAtual],
  );

  const datasParaComparacaoApi = useMemo(() => {
    if (periodoTipo === 'PERSONALIZADO') {
      return { data_inicio: isoDate10(dataInicio), data_fim: isoDate10(dataFim) };
    }
    return resolvePeriodoParaDatas({
      tipo: periodoTipo,
      mes: periodoMes,
      ano: periodoAno,
      trimestre: periodoTrimestre,
      semestre: periodoSemestre,
      data_inicio: '',
      data_fim: '',
    });
  }, [periodoTipo, periodoMes, periodoAno, periodoTrimestre, periodoSemestre, dataInicio, dataFim]);

  const onTipoPeriodoChange = useCallback(
    (novo: PeriodoTipoApuracao) => {
      if (novo === 'PERSONALIZADO') {
        dataInicioLiveRef.current = String(dataInicio).trim();
        dataFimLiveRef.current = String(dataFim).trim();
        setPeriodoTipo('PERSONALIZADO');
        return;
      }
      let mesRef = periodoMes;
      let anoRef = periodoAno;
      if (periodoTipo === 'PERSONALIZADO') {
        const inf = interpretarDatasComoMesFiscal(dataInicio, dataFim);
        if (inf) {
          mesRef = inf.mes;
          anoRef = inf.ano;
          setPeriodoMes(inf.mes);
          setPeriodoAno(inf.ano);
        } else {
          const d0 = isoDate10(dataInicio);
          if (d0.length >= 10) {
            const y = Number(d0.slice(0, 4));
            const m = Number(d0.slice(5, 7));
            if (Number.isFinite(y) && Number.isFinite(m) && m >= 1 && m <= 12) {
              mesRef = m;
              anoRef = y;
              setPeriodoMes(m);
              setPeriodoAno(y);
            }
          }
        }
      }
      if (novo === 'TRIMESTRAL') {
        setPeriodoTrimestre(Math.max(1, Math.min(4, Math.ceil(mesRef / 3))));
      }
      if (novo === 'SEMESTRAL') {
        setPeriodoSemestre(mesRef <= 6 ? 1 : 2);
      }
      if (novo === 'ANUAL') {
        setPeriodoAno(anoRef);
      }
      setPeriodoTipo(novo);
    },
    [periodoTipo, periodoMes, periodoAno, dataInicio, dataFim],
  );

  const buildParamsRef = useRef(buildParams);
  buildParamsRef.current = buildParams;
  const apuracaoFiltrosKeyRef = useRef(apuracaoQueryKey);
  apuracaoFiltrosKeyRef.current = apuracaoQueryKey;

  const apuracaoFetchCtrlRef = useRef<AbortController | null>(null);
  const apuracaoReqGenRef = useRef(0);
  const apuracaoDebounceTimerRef = useRef<number | undefined>(undefined);

  const abortarRequisicaoApuracaoEmVoo = useCallback(() => {
    apuracaoFetchCtrlRef.current?.abort();
    apuracaoFetchCtrlRef.current = null;
  }, []);

  const iniciarCancelavelApuracao = useCallback(() => {
    apuracaoFetchCtrlRef.current?.abort();
    const c = new AbortController();
    apuracaoFetchCtrlRef.current = c;
    return c;
  }, []);

  const sincronizarRefsDatasParaRequisicao = useCallback(() => {
    if (periodoTipo === 'PERSONALIZADO') {
      dataInicioLiveRef.current = String(dataInicio ?? '').trim();
      dataFimLiveRef.current = String(dataFim ?? '').trim();
      return;
    }
    const ui: PeriodoApuracaoUi = {
      tipo: periodoTipo,
      mes: periodoMes,
      ano: periodoAno,
      trimestre: periodoTrimestre,
      semestre: periodoSemestre,
      data_inicio: '',
      data_fim: '',
    };
    const r = resolvePeriodoParaDatas(ui);
    dataInicioLiveRef.current = r.data_inicio;
    dataFimLiveRef.current = r.data_fim;
  }, [periodoTipo, periodoMes, periodoAno, periodoTrimestre, periodoSemestre, dataInicio, dataFim]);

  const executaApuracao = useCallback(
    async (expectedKey: string) => {
      sincronizarRefsDatasParaRequisicao();
      const p0 = buildParamsRef.current();
      if (!String(p0.data_inicio).trim() || !String(p0.data_fim).trim()) {
        setError('Informe data inicial e data final.');
        setLoading(false);
        return;
      }
      if (isoDate10(p0.data_inicio) > isoDate10(p0.data_fim)) {
        setError('Data inicial não pode ser maior que a data final.');
        setLoading(false);
        return;
      }
      const myGen = ++apuracaoReqGenRef.current;
      const ac = iniciarCancelavelApuracao();
      setLoading(true);
      setError(null);
      const p = { ...buildParamsRef.current() };
      if (import.meta.env.DEV) {
        console.log('APURACAO PARAMS ENVIADOS', { ...p });
      }
      try {
        if (apuracaoFiltrosKeyRef.current !== expectedKey) return;
        const d = await apuracaoService.get(p, { signal: ac.signal });
        if (apuracaoFiltrosKeyRef.current !== expectedKey) return;
        if (myGen !== apuracaoReqGenRef.current) return;
        if (!d || typeof d !== 'object' || !('cards' in d)) {
          setError('Resposta inválida da API de apuração (sem dados de cards).');
          setData(null);
          return;
        }
        const payload = d as ApuracaoFiscalPayload;
        if (!filtrosEchoConfere(p, payload)) {
          setError(
            'O período devolvido pela API não confere com o enviado (parâmetros ausentes no servidor ou resposta fora de ordem). Tente Ctrl+F5.',
          );
          setData(null);
          return;
        }
        setData(payload);
      } catch (e) {
        if (isApuracaoAbortError(e)) return;
        if (apuracaoFiltrosKeyRef.current === expectedKey && myGen === apuracaoReqGenRef.current) {
          setError(apiErrorMessage(e, { fallback: 'Não foi possível apurar.' }));
          setData(null);
        }
      } finally {
        if (myGen === apuracaoReqGenRef.current) setLoading(false);
      }
    },
    [iniciarCancelavelApuracao, sincronizarRefsDatasParaRequisicao],
  );

  const apurar = useCallback(() => {
    sincronizarRefsDatasParaRequisicao();
    if (apuracaoDebounceTimerRef.current !== undefined) {
      window.clearTimeout(apuracaoDebounceTimerRef.current);
      apuracaoDebounceTimerRef.current = undefined;
    }
    void executaApuracao(apuracaoQueryKey);
  }, [apuracaoQueryKey, executaApuracao, sincronizarRefsDatasParaRequisicao]);

  /** Debounce + cancelamento: troca de filtro aborta GET anterior; payload usa `data*LiveRef` via `buildParams`. */
  useEffect(() => {
    const scheduledKey = apuracaoQueryKey;
    if (apuracaoDebounceTimerRef.current !== undefined) {
      window.clearTimeout(apuracaoDebounceTimerRef.current);
    }
    apuracaoDebounceTimerRef.current = window.setTimeout(() => {
      apuracaoDebounceTimerRef.current = undefined;
      void executaApuracao(scheduledKey);
    }, 400);
    return () => {
      if (apuracaoDebounceTimerRef.current !== undefined) {
        window.clearTimeout(apuracaoDebounceTimerRef.current);
        apuracaoDebounceTimerRef.current = undefined;
      }
      abortarRequisicaoApuracaoEmVoo();
    };
  }, [apuracaoQueryKey, executaApuracao, abortarRequisicaoApuracaoEmVoo]);

  const apuracaoCards = data?.cards;
  const fontes = data?.fontes;
  const diagFontes = data?.diagnostico_fontes;
  const num = (v: unknown) => {
    const x = Number(v);
    return Number.isFinite(x) ? x : 0;
  };
  const totalNotas = num(apuracaoCards?.notas_entrada) + num(apuracaoCards?.notas_saida);
  const candidatasTipo = num(fontes?.candidatas_aplicaveis_tipo);
  const histSaidaSemEmpresa = num(fontes?.saidas_historicas_periodo_sem_filtro_empresa);
  const histEntradaSemEmpresa = num(fontes?.entradas_historicas_periodo_sem_filtro_empresa);
  /** API antiga sem `fontes`: usa contagens do encadeamento de diagnóstico. */
  const histSaidaParaBanner = Math.max(histSaidaSemEmpresa, num(diagFontes?.saidas_historicas_no_periodo));
  const histImportadasNoPeriodoPorTipo =
    (tipo !== 'ENTRADA' ? histSaidaParaBanner : 0) + (tipo !== 'SAIDA' ? histEntradaSemEmpresa : 0);
  const exibirBannerNenhumaNfe =
    !!data && totalNotas === 0 && candidatasTipo === 0 && histImportadasNoPeriodoPorTipo === 0;
  const exibirBannerDocumentosForaDoResultado =
    !!data && totalNotas === 0 && !exibirBannerNenhumaNfe;

  const periodoDiverge =
    !!data?.filtros &&
    (isoDate10(datasParaComparacaoApi.data_inicio) !== isoDate10(data.filtros.data_inicio) ||
      isoDate10(datasParaComparacaoApi.data_fim) !== isoDate10(data.filtros.data_fim));

  return (
    <div className="max-w-[1600px] mx-auto space-y-8 md:space-y-10 pb-12 px-2 sm:px-4 lg:px-6">
      <div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">Apuração Fiscal</h1>
        <p className="text-xs font-mono text-muted-foreground/90 mt-2">
          <span className="text-foreground/80">GET /api/fiscal/apuracao/</span>
        </p>
        <p className="text-sm text-muted-foreground mt-3 max-w-3xl leading-relaxed">
          Painel gerencial on-demand (pré-SPED). Tributos consolidados a partir de NF-e importada (XML). NF interna do ERP
          entra quando filtrada (modelo INTERNA). Ajuste o período se as notas forem de outro mês; a consulta atualiza
          após alterar filtros ou use <span className="font-medium text-foreground">Apurar</span>.
        </p>
      </div>

      <div className="rounded-2xl border border-border/60 bg-card shadow-md ring-1 ring-border/20 p-6 md:p-8 space-y-6">
        <div className="flex flex-col gap-4">
          <h2 className="text-sm font-semibold text-foreground tracking-tight">Ações e filtros</h2>
          <div className="flex flex-wrap gap-2 md:gap-3">
            <button type="button" className="erp-btn-primary" disabled={loading} onClick={apurar}>
              {loading ? 'Apurando…' : 'Apurar'}
            </button>
            <button
              type="button"
              className="erp-btn-outline"
              disabled={loading}
              onClick={() => {
                setEmpresaId('');
                const agora = new Date();
                const m = agora.getMonth() + 1;
                const y = agora.getFullYear();
                const r = calcularPeriodoMensal(y, m);
                setPeriodoTipo('MENSAL');
                setPeriodoMes(m);
                setPeriodoAno(y);
                setPeriodoTrimestre(Math.ceil(m / 3));
                setPeriodoSemestre(m <= 6 ? 1 : 2);
                dataInicioLiveRef.current = r.data_inicio;
                dataFimLiveRef.current = r.data_fim;
                setDataInicio(r.data_inicio);
                setDataFim(r.data_fim);
                setTipo('AMBOS');
                setFonte('TODOS');
                setStatus('');
                setCfop('');
                setNcm('');
                setModelo('');
                setIncluirCanceladas(false);
                setData(null);
                setError(null);
              }}
            >
              Limpar filtros
            </button>
            <button
              type="button"
              className="erp-btn-outline"
              disabled={!data || loading}
              onClick={() => {
                sincronizarRefsDatasParaRequisicao();
                void apuracaoService.exportCsvApuracao(buildParams());
              }}
            >
              Exportar CSV da apuração
            </button>
            <button
              type="button"
              className="erp-btn-outline"
              disabled={!data || loading}
              onClick={() => {
                sincronizarRefsDatasParaRequisicao();
                void apuracaoService.exportCsvAlertas(buildParams());
              }}
            >
              Exportar CSV dos alertas
            </button>
            <button type="button" className="erp-btn-outline opacity-60 cursor-not-allowed" disabled title={SPED_TXT_TOOLTIP}>
              Gerar TXT EFD ICMS/IPI — em preparação
            </button>
            <button type="button" className="erp-btn-outline opacity-60 cursor-not-allowed" disabled title={SPED_TXT_TOOLTIP}>
              Gerar TXT EFD Contribuições — em preparação
            </button>
          </div>
        </div>

        <div className="border-t border-border/50 pt-6 space-y-5">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Parâmetros da consulta</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-5">
            <div className="sm:col-span-2 lg:col-span-3 xl:col-span-4">
              <label className="erp-label">Tipo de período</label>
              <select
                className="erp-select mt-1 w-full max-w-xl"
                value={periodoTipo}
                onChange={(e) => onTipoPeriodoChange(e.target.value as PeriodoTipoApuracao)}
              >
                <option value="MENSAL">Mensal</option>
                <option value="TRIMESTRAL">Trimestral</option>
                <option value="SEMESTRAL">Semestral</option>
                <option value="ANUAL">Anual</option>
                <option value="PERSONALIZADO">Personalizado</option>
              </select>
            </div>
            {periodoTipo === 'MENSAL' ? (
              <>
                <div>
                  <label className="erp-label">Mês</label>
                  <select
                    className="erp-select mt-1 w-full"
                    value={periodoMes}
                    onChange={(e) => setPeriodoMes(Number(e.target.value))}
                  >
                    {Array.from({ length: 12 }, (_, i) => {
                      const m = i + 1;
                      return (
                        <option key={m} value={m}>
                          {MESES_PT[m]}
                        </option>
                      );
                    })}
                  </select>
                </div>
                <div>
                  <label className="erp-label">Ano</label>
                  <input
                    type="number"
                    className="erp-input mt-1 w-full"
                    min={2000}
                    max={2100}
                    step={1}
                    value={periodoAno}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setPeriodoAno(Number.isFinite(v) ? Math.min(2100, Math.max(2000, Math.floor(v))) : anoCorrente);
                    }}
                  />
                </div>
              </>
            ) : null}
            {periodoTipo === 'TRIMESTRAL' ? (
              <>
                <div>
                  <label className="erp-label">Trimestre</label>
                  <select
                    className="erp-select mt-1 w-full"
                    value={periodoTrimestre}
                    onChange={(e) => setPeriodoTrimestre(Number(e.target.value))}
                  >
                    <option value={1}>1º trimestre — Janeiro a Março</option>
                    <option value={2}>2º trimestre — Abril a Junho</option>
                    <option value={3}>3º trimestre — Julho a Setembro</option>
                    <option value={4}>4º trimestre — Outubro a Dezembro</option>
                  </select>
                </div>
                <div>
                  <label className="erp-label">Ano</label>
                  <input
                    type="number"
                    className="erp-input mt-1 w-full"
                    min={2000}
                    max={2100}
                    step={1}
                    value={periodoAno}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setPeriodoAno(Number.isFinite(v) ? Math.min(2100, Math.max(2000, Math.floor(v))) : anoCorrente);
                    }}
                  />
                </div>
              </>
            ) : null}
            {periodoTipo === 'SEMESTRAL' ? (
              <>
                <div>
                  <label className="erp-label">Semestre</label>
                  <select
                    className="erp-select mt-1 w-full"
                    value={periodoSemestre}
                    onChange={(e) => setPeriodoSemestre(Number(e.target.value))}
                  >
                    <option value={1}>1º semestre — Janeiro a Junho</option>
                    <option value={2}>2º semestre — Julho a Dezembro</option>
                  </select>
                </div>
                <div>
                  <label className="erp-label">Ano</label>
                  <input
                    type="number"
                    className="erp-input mt-1 w-full"
                    min={2000}
                    max={2100}
                    step={1}
                    value={periodoAno}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setPeriodoAno(Number.isFinite(v) ? Math.min(2100, Math.max(2000, Math.floor(v))) : anoCorrente);
                    }}
                  />
                </div>
              </>
            ) : null}
            {periodoTipo === 'ANUAL' ? (
              <div>
                <label className="erp-label">Ano</label>
                <input
                  type="number"
                  className="erp-input mt-1 w-full"
                  min={2000}
                  max={2100}
                  step={1}
                  value={periodoAno}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setPeriodoAno(Number.isFinite(v) ? Math.min(2100, Math.max(2000, Math.floor(v))) : anoCorrente);
                  }}
                />
              </div>
            ) : null}
            {periodoTipo === 'PERSONALIZADO' ? (
              <>
                <div>
                  <label className="erp-label">Data inicial</label>
                  <input
                    type="date"
                    className="erp-input mt-1 w-full"
                    value={dataInicio}
                    onChange={(e) => {
                      const v = e.target.value;
                      dataInicioLiveRef.current = v;
                      setDataInicio(v);
                    }}
                  />
                </div>
                <div>
                  <label className="erp-label">Data final</label>
                  <input
                    type="date"
                    className="erp-input mt-1 w-full"
                    value={dataFim}
                    onChange={(e) => {
                      const v = e.target.value;
                      dataFimLiveRef.current = v;
                      setDataFim(v);
                    }}
                  />
                </div>
              </>
            ) : null}
            <div>
              <label className="erp-label">Empresa</label>
              <select className="erp-select mt-1 w-full" value={empresaId} onChange={(e) => setEmpresaId(e.target.value)}>
                <option value="">Todas</option>
                {empresas.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.nome_fantasia || e.razao_social}
                  </option>
                ))}
              </select>
            </div>
          <div>
            <label className="erp-label">Tipo</label>
            <select className="erp-select mt-1 w-full" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="AMBOS">Entrada e saída</option>
              <option value="ENTRADA">Entrada</option>
              <option value="SAIDA">Saída</option>
            </select>
          </div>
          <div>
            <label className="erp-label">Fonte dos documentos</label>
            <select
              className="erp-select mt-1 w-full"
              value={fonte}
              onChange={(e) => setFonte(e.target.value as 'TODOS' | 'OPERACIONAIS' | 'HISTORICOS')}
            >
              <option value="TODOS">Todos válidos: operacionais produção + base DF-e importada</option>
              <option value="OPERACIONAIS">Operacionais produção (ERP)</option>
              <option value="HISTORICOS">Base DF-e importada (XML)</option>
            </select>
            <p className="text-xs text-muted-foreground mt-1">
              A apuração considera apenas documentos de produção, autorizados e fiscalmente válidos. Documentos de
              homologação são sempre excluídos.
            </p>
          </div>
          <div>
            <label className="erp-label">Status</label>
            <input
              className="erp-input mt-1 w-full"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              placeholder="NF saída histórica (ex.: autorizada)"
            />
          </div>
          <div>
            <label className="erp-label">CFOP</label>
            <input className="erp-input mt-1 w-full" value={cfop} onChange={(e) => setCfop(e.target.value)} placeholder="ex.: 5102" />
          </div>
          <div>
            <label className="erp-label">NCM</label>
            <input className="erp-input mt-1 w-full" value={ncm} onChange={(e) => setNcm(e.target.value)} />
          </div>
          <div>
            <label className="erp-label">Modelo documento</label>
            <input className="erp-input mt-1 w-full" value={modelo} onChange={(e) => setModelo(e.target.value)} placeholder="55, 65 ou INTERNA" />
          </div>
          <div className="flex items-end gap-2">
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input type="checkbox" checked={incluirCanceladas} onChange={(e) => setIncluirCanceladas(e.target.checked)} />
              Incluir canceladas
            </label>
          </div>
        </div>
        </div>

        <div
          className={`rounded-xl px-4 py-3 space-y-1 text-sm ${
            periodoDiverge
              ? 'border border-amber-300/90 bg-amber-50 text-amber-950 shadow-sm'
              : 'border border-border/50 bg-muted/15 text-foreground'
          }`}
        >
          <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="font-semibold text-foreground shrink-0">Período selecionado:</span>
            <span className="font-medium">{rotuloPeriodoSelecionado}</span>
          </p>
          {data?.filtros ? (
            <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="font-semibold shrink-0">Período apurado:</span>
              <span className="tabular-nums font-medium">
                {formatISODatePtBR(data.filtros.data_inicio)} a {formatISODatePtBR(data.filtros.data_fim)}
              </span>
              {periodoDiverge ? (
                <span className="text-xs font-medium text-amber-900">
                  (diverge do selecionado — confira cache ou aguarde nova resposta)
                </span>
              ) : null}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Intervalo da consulta: {formatISODatePtBR(datasParaComparacaoApi.data_inicio)} a{' '}
              {formatISODatePtBR(datasParaComparacaoApi.data_fim)}. Aguarde a apuração ou clique em Apurar.
            </p>
          )}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      {data && (
        <>
          {exibirBannerNenhumaNfe ? (
            <div className="rounded-md border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
              Nenhuma NF-e encontrada no período selecionado para os filtros informados.
            </div>
          ) : null}
          {exibirBannerDocumentosForaDoResultado ? (
            <div className="rounded-md border border-sky-200 bg-sky-50/90 px-4 py-3 text-sm text-sky-950">
              Existem NF importadas ou candidatas no período, porém nenhuma nota entrou neste resultado. Confira o
              filtro de empresa (emitente/destinatário nas NF históricas), status, CFOP, NCM, modelo e a aba Alertas —
              em especial o aviso quando a empresa selecionada exclui todas as NF-e do XML.
            </div>
          ) : null}

          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-foreground tracking-tight">Visão geral</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 md:gap-6">
              <KpiCardHero titulo="Notas de entrada" valor={num(apuracaoCards?.notas_entrada)} sub="NF-es incluídas na apuração (lado entrada)" />
              <KpiCardHero titulo="Notas de saída" valor={num(apuracaoCards?.notas_saida)} sub="NF-es incluídas na apuração (lado saída)" />
              <KpiCardHero
                titulo="Itens fiscais"
                valor={num(data.resumo?.entrada?.quantidade_itens) + num(data.resumo?.saida?.quantidade_itens)}
                sub="Linhas de item somadas nos documentos"
              />
              <KpiCardHero titulo="Valor total de entradas" valor={fmtMoney(apuracaoCards?.valor_entradas)} sub="Documentos no período" />
              <KpiCardHero titulo="Valor total de saídas" valor={fmtMoney(apuracaoCards?.valor_saidas)} sub="Documentos no período" />
              <KpiCardHero titulo="Eventos pendentes" valor={apuracaoCards?.eventos_pendentes ?? 0} sub="Cancelamentos e eventos a tratar" />
              <KpiCardHero titulo="Alertas fiscais" valor={apuracaoCards?.alertas ?? 0} sub="Quantidade na aba Alertas" />
            </div>
          </div>

          <div className="rounded-xl bg-muted/25 p-1.5 flex flex-wrap gap-1 border border-border/50 shadow-inner">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`px-4 py-2.5 text-sm rounded-lg transition-colors ${
                  tab === t.id
                    ? 'bg-card text-foreground font-semibold shadow-sm ring-1 ring-border/60'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="rounded-2xl border border-border/60 bg-card shadow-md ring-1 ring-border/15 p-6 md:p-10">
            {tab === 'resumo' && (
              <div className="space-y-10">
                <div>
                  <h3 className="text-base font-semibold text-foreground mb-4">Resumo por lado</h3>
                  <div className="grid lg:grid-cols-2 gap-6 lg:gap-8">
                    <AcumuloTable titulo="Entradas" a={data.resumo?.entrada} />
                    <AcumuloTable titulo="Saídas" a={data.resumo?.saida} />
                  </div>
                </div>
                <SaldoGerencialTable saldo={data.resumo?.saldo_gerencial_saida_menos_entrada} />
              </div>
            )}

            {tab === 'icms_ipi' && (
              <div className="space-y-10">
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">ICMS / IPI</h3>
                  <p className="text-sm text-muted-foreground max-w-3xl mb-6">
                    Conferência lado a lado. O saldo é <span className="font-medium text-foreground">saída menos entrada</span> nos
                    totais do item.
                  </p>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
                    <LadoFiscalReadonlyCard titulo="Entrada" rows={icmsIpiRows(data.icms_ipi?.entrada)} />
                    <LadoFiscalReadonlyCard
                      titulo="Saldo"
                      rows={[
                        {
                          label: 'Base ICMS',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.icms_ipi?.entrada, data.icms_ipi?.saida, 'base_icms')),
                        },
                        {
                          label: 'ICMS',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.icms_ipi?.entrada, data.icms_ipi?.saida, 'valor_icms')),
                        },
                        {
                          label: 'Base IPI',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.icms_ipi?.entrada, data.icms_ipi?.saida, 'base_ipi')),
                        },
                        {
                          label: 'IPI',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.icms_ipi?.entrada, data.icms_ipi?.saida, 'valor_ipi')),
                        },
                        {
                          label: 'Valor dos documentos',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.icms_ipi?.entrada, data.icms_ipi?.saida, 'valor_documentos')),
                        },
                        {
                          label: 'Valor dos produtos',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.icms_ipi?.entrada, data.icms_ipi?.saida, 'valor_produtos')),
                        },
                      ]}
                      footer="Saldo gerencial: saída menos entrada."
                    />
                    <LadoFiscalReadonlyCard titulo="Saída" rows={icmsIpiRows(data.icms_ipi?.saida)} />
                  </div>
                </div>
                <div>
                  <h3 className="text-base font-semibold text-foreground mb-4">Acúmulo detalhado (referência)</h3>
                  <div className="grid lg:grid-cols-2 gap-6 lg:gap-8">
                    <AcumuloTable titulo="Entradas" a={data.icms_ipi?.entrada} />
                    <AcumuloTable titulo="Saídas" a={data.icms_ipi?.saida} />
                  </div>
                </div>
                {data.icms_ipi?.comparativo_documento?.observacao ? (
                  <p className="text-sm text-muted-foreground leading-relaxed border-l-4 border-sky-300/80 pl-4 py-1">
                    {data.icms_ipi.comparativo_documento.observacao}
                  </p>
                ) : null}
              </div>
            )}

            {tab === 'pis_cofins' && (
              <div className="space-y-10">
                <div>
                  <h3 className="text-lg font-semibold text-foreground mb-2">PIS / COFINS</h3>
                  <p className="text-sm text-muted-foreground max-w-3xl mb-6">
                    Entrada costuma concentrar bases de crédito; saída, de débito. O saldo segue a mesma lógica de saída menos
                    entrada.
                  </p>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
                    <LadoFiscalReadonlyCard
                      titulo="Entrada"
                      rows={pisCofinsRows(data.pis_cofins?.entrada)}
                      footer="Possíveis créditos conforme movimento de entrada."
                    />
                    <LadoFiscalReadonlyCard
                      titulo="Saldo"
                      rows={[
                        {
                          label: 'Base PIS',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.pis_cofins?.entrada, data.pis_cofins?.saida, 'base_pis')),
                        },
                        { label: 'PIS', value: fmtMoney(saldoSaidaMenosEntrada(data.pis_cofins?.entrada, data.pis_cofins?.saida, 'valor_pis')) },
                        {
                          label: 'Base COFINS',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.pis_cofins?.entrada, data.pis_cofins?.saida, 'base_cofins')),
                        },
                        {
                          label: 'COFINS',
                          value: fmtMoney(saldoSaidaMenosEntrada(data.pis_cofins?.entrada, data.pis_cofins?.saida, 'valor_cofins')),
                        },
                      ]}
                      footer="Saldo gerencial: saída menos entrada."
                    />
                    <LadoFiscalReadonlyCard
                      titulo="Saída"
                      rows={pisCofinsRows(data.pis_cofins?.saida)}
                      footer="Possíveis débitos conforme movimento de saída."
                    />
                  </div>
                </div>
                <div>
                  <h3 className="text-base font-semibold text-foreground mb-4">Acúmulo detalhado (referência)</h3>
                  <div className="grid lg:grid-cols-2 gap-6 lg:gap-8">
                    <AcumuloTable titulo="Entradas" a={data.pis_cofins?.entrada} />
                    <AcumuloTable titulo="Saídas" a={data.pis_cofins?.saida} />
                  </div>
                </div>
              </div>
            )}

            {tab === 'reforma' && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-foreground tracking-tight">Reforma Tributária</h3>
                <ReformaTributariaPainel
                  r={data.reforma_tributaria}
                  cardsKpi={apuracaoCards}
                  fonte={fonte}
                  tipo={tipo}
                  fontes={fontes}
                  temNotasNoPeriodo={totalNotas > 0}
                  diagnosticoReforma={data.diagnostico_reforma}
                />
              </div>
            )}

            {tab === 'efd_icms' && (
              <div className="space-y-6">
                <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
                  Indicadores pré-SPED para montagem futura do EFD ICMS/IPI. Valores são contagens e pendências de cadastro,
                  não substituem o PVA oficial.
                </p>
                <EfdIcmsIpiPainel efd={data.efd_icms_ipi} totalNotas={totalNotas} />
              </div>
            )}

            {tab === 'efd_contrib' && (
              <div className="space-y-6">
                <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
                  Indicadores pré-SPED para EFD Contribuições (PIS/COFINS). Use como conferência de completude da base.
                </p>
                <EfdContribuicoesPainel efd={data.efd_contribuicoes} totalNotas={totalNotas} />
              </div>
            )}

            {tab === 'agrupamentos' && (
              <div className="space-y-10">
                <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
                  Tabelas somente leitura. Cada bloco corresponde a uma chave de agrupamento (CFOP, NCM, CST, participante,
                  etc.) com totais de itens e tributos.
                </p>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-8 gap-y-10">
                  {AGRUPAMENTO_LABELS.map(({ key, titulo }) => (
                    <AgrupTable key={key} titulo={titulo} rows={data.agrupamentos?.[key]} />
                  ))}
                </div>
              </div>
            )}

            {tab === 'alertas' && (
              <div className="space-y-4">
                {!data.alertas?.length ? (
                  <p className="text-sm text-muted-foreground border border-dashed border-border/80 rounded-2xl px-6 py-12 text-center bg-muted/10">
                    Nenhum alerta fiscal encontrado.
                  </p>
                ) : (
                  <div className="rounded-2xl border border-border/70 overflow-hidden shadow-sm">
                    <div className="overflow-auto max-h-[min(640px,70vh)]">
                      <table className="w-full text-sm min-w-[960px]">
                        <thead className="sticky top-0 z-20 bg-muted/95 backdrop-blur-sm border-b border-border shadow-sm">
                          <tr>
                            <th className="text-left font-semibold px-4 py-3 whitespace-nowrap">Severidade</th>
                            <th className="text-left font-semibold px-4 py-3 whitespace-nowrap">Tipo</th>
                            <th className="text-left font-semibold px-4 py-3 whitespace-nowrap">Documento</th>
                            <th className="text-left font-semibold px-4 py-3 whitespace-nowrap">Item</th>
                            <th className="text-left font-semibold px-4 py-3 min-w-[220px]">Mensagem</th>
                            <th className="text-left font-semibold px-4 py-3 whitespace-nowrap">Origem</th>
                            <th className="text-left font-semibold px-4 py-3 min-w-[180px]">Ação sugerida</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/60">
                          {data.alertas.map((a: ApuracaoFiscalAlerta, i: number) => (
                            <tr key={i} className="hover:bg-muted/20">
                              <td className="px-4 py-2.5 align-top">
                                <span className={`${severidadeBadgeClass(a.severidade)} text-xs font-medium`}>
                                  {severidadeLabel(a.severidade)}
                                </span>
                              </td>
                              <td className="font-mono text-xs px-4 py-2.5 align-top whitespace-nowrap">
                                {a.codigo === 'EVENTO_CANCEL_PENDENTE' ? 'Evento de cancelamento pendente' : a.codigo}
                              </td>
                              <td className="font-mono text-xs px-4 py-2.5 align-top whitespace-nowrap">
                                {a.documento_id != null ? `#${a.documento_id}` : '—'}
                              </td>
                              <td className="text-xs px-4 py-2.5 align-top tabular-nums">{a.item_id ?? '—'}</td>
                              <td className="max-w-md px-4 py-2.5 align-top text-foreground/90">{a.mensagem}</td>
                              <td
                                className="text-xs text-muted-foreground px-4 py-2.5 align-top max-w-[160px] truncate"
                                title={a.documento_tipo ?? undefined}
                              >
                                {a.documento_tipo ?? '—'}
                              </td>
                              <td className="text-xs text-muted-foreground px-4 py-2.5 align-top max-w-[240px]">
                                {a.acao_sugerida ?? '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {tab === 'info_tecnica' && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Conteúdo para suporte e auditoria. Cada bloco abaixo fica recolhido até você expandir.
                </p>
                <PainelInformacoesTecnicas data={data} />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default ApuracaoFiscalPage;
