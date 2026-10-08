import { Link } from 'react-router-dom';
import {
  dashboardService,
  type DashboardBIModulo,
  type DashboardModuloBI,
} from '@/services/api/dashboard';
import { useDashboardBI, type DashboardBIFetcher } from '@/hooks/useDashboardBI';
import { useDashboardPermissoes } from '@/hooks/useDashboardPermissoes';
import { BIPageLayout } from '@/components/bi/BIPageLayout';
import { BIFilterBar } from '@/components/bi/BIFilterBar';
import { BIKpiCard } from '@/components/bi/BIKpiCard';
import { BIKpiHeroCard } from '@/components/bi/BIKpiHeroCard';
import { BIChartCard } from '@/components/bi/BIChartCard';
import { BIRankingList } from '@/components/bi/BIRankingList';
import { BIAlertList } from '@/components/bi/BIAlertList';
import { BILastDocuments } from '@/components/bi/BILastDocuments';
import { BIAccessDenied } from '@/components/bi/BIAccessDenied';
import { BILoadingState } from '@/components/bi/BILoadingState';
import { BIErrorState } from '@/components/bi/BIErrorState';
import { BIPreparationState } from '@/components/bi/BIPreparationState';
import { BIModuleNav } from '@/components/bi/BIModuleNav';
import { MODULO_HERO_KPI } from '@/components/bi/dashboardBiConfig';

const FETCHERS: Record<DashboardBIModulo, DashboardBIFetcher> = {
  comercial: dashboardService.getComercial,
  fiscal: dashboardService.getFiscal,
  estoque: dashboardService.getEstoque,
  expedicao: dashboardService.getExpedicao,
  compras: dashboardService.getCompras,
  qualidade: dashboardService.getQualidade,
  financeiro: dashboardService.getFinanceiro,
};

const MODULO_LABELS: Record<DashboardBIModulo, string> = {
  comercial: 'Comercial',
  fiscal: 'Fiscal',
  estoque: 'Estoque',
  expedicao: 'Expedição',
  compras: 'Compras',
  qualidade: 'Qualidade',
  financeiro: 'Financeiro',
};

const MODULO_SUBTITLES: Record<DashboardBIModulo, string> = {
  comercial: 'Pedidos, propostas e valor a faturar',
  fiscal: 'NF-e produção/homologação, DF-e recebidos, SEFAZ e certificados',
  estoque: 'Saldos, rastreabilidade, alertas e atendimentos',
  expedicao: 'Separação, retirada, trânsito e entregas',
  compras: 'Pedidos de compra, NF-e de entrada e CT-e',
  qualidade: 'Certificados, rastreabilidade, CF fornecedor e corridas',
  financeiro: 'Recebimentos, pagamentos, vencimentos e alertas operacionais',
};

type DashboardModuloViewProps = {
  modulo: DashboardBIModulo;
};

function splitKpis(modulo: DashboardBIModulo, data: DashboardModuloBI) {
  const heroId = data.hero_kpi_id ?? MODULO_HERO_KPI[modulo];
  const hero = heroId ? data.kpis.find((k) => k.id === heroId) : null;
  const secondary = data.kpis.filter((k) => k.id !== heroId);
  return { hero, secondary };
}

function ModuloContent({ modulo, data }: { modulo: DashboardBIModulo; data: DashboardModuloBI }) {
  const graficos = data.graficos ?? [];
  const rankings = data.rankings ?? [];
  const alertas = data.alertas ?? [];
  const ultimos = data.ultimos ?? [];
  const links = data.links ?? [];
  const kpis = data.kpis ?? [];

  if (data.em_preparacao) {
    return (
      <BIPreparationState
        title="Financeiro em preparação"
        message={
          data.mensagem ??
          'Contas a receber serão geradas pela NF-e de saída autorizada em produção. Contas a pagar serão geradas pela NF-e de entrada do fornecedor.'
        }
      />
    );
  }

  const { hero, secondary } = splitKpis(modulo, { ...data, kpis });

  return (
    <>
      {links.length > 0 ? (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {links.map((lnk) => (
            <Link
              key={lnk.id}
              to={lnk.link}
              className="erp-card p-4 hover:border-primary/40 transition-colors block border-l-4 border-l-primary/40"
            >
              <p className="text-sm font-semibold text-foreground">{lnk.titulo}</p>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{lnk.descricao}</p>
            </Link>
          ))}
        </section>
      ) : null}

      <section className="mb-8 flex flex-col gap-4 min-w-0">
        {hero ? (
          <div className="min-w-0 w-full">
            <BIKpiHeroCard kpi={hero} />
          </div>
        ) : null}
        {secondary.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 min-w-0">
            {secondary.map((kpi) => (
              <BIKpiCard key={kpi.id} kpi={kpi} />
            ))}
          </div>
        ) : null}
      </section>

      {graficos.length > 0 ? (
        <section className="mb-8 min-w-0">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Gráficos</h2>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 min-w-0">
            {graficos.map((chart) => (
              <BIChartCard key={chart.id} chart={chart} />
            ))}
          </div>
        </section>
      ) : null}

      {rankings.length > 0 ? (
        <section className="mb-8">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Rankings</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {rankings.map((ranking) => (
              <BIRankingList key={ranking.id} ranking={ranking} />
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-w-0">
        <BIAlertList alertas={alertas} compact />
        <BILastDocuments itens={ultimos} />
      </section>
    </>
  );
}

export default function DashboardModuloView({ modulo }: DashboardModuloViewProps) {
  const { permissoes } = useDashboardPermissoes();
  const {
    data,
    loading,
    error,
    forbidden,
    unauthorized,
    appliedFilters,
    applyFilters,
    clearFilters,
    reload,
  } = useDashboardBI(modulo, FETCHERS[modulo]);

  const showEmpresaFilter = modulo === 'comercial' || modulo === 'fiscal';

  if (forbidden) {
    return <BIAccessDenied modulo={MODULO_LABELS[modulo]} />;
  }

  if (unauthorized && !loading) {
    return (
      <BIPageLayout
        title={`BI ${MODULO_LABELS[modulo]}`}
        subtitle={MODULO_SUBTITLES[modulo]}
        nav={<BIModuleNav permissoes={permissoes} />}
      >
        <BIErrorState message={error ?? undefined} />
      </BIPageLayout>
    );
  }

  return (
    <BIPageLayout
      title={`BI ${MODULO_LABELS[modulo]}`}
      subtitle={MODULO_SUBTITLES[modulo]}
      periodo={data?.periodo}
      nav={<BIModuleNav permissoes={permissoes} />}
      filters={
        <BIFilterBar
          filters={appliedFilters}
          onApply={applyFilters}
          onClear={clearFilters}
          showEmpresa={showEmpresaFilter}
        />
      }
    >
      {loading ? <BILoadingState /> : null}
      {!loading && error ? <BIErrorState message={error} onRetry={() => void reload()} /> : null}
      {!loading && !error && data ? <ModuloContent modulo={modulo} data={data} /> : null}
    </BIPageLayout>
  );
}
