import type { BIChart } from '@/services/api/dashboard';
import { hasChartData, chartRowsFromChart } from '@/lib/biChartData';
import { BIStatusChart } from './BIStatusChart';

const CHART_WRAPPER_CLASS = 'w-full min-w-0 min-h-[280px] h-[320px]';

export function BIChartCard({
  chart,
  emptyTitle,
  emptyMessage,
}: {
  chart: BIChart;
  emptyTitle?: string;
  emptyMessage?: string;
}) {
  const rows = chartRowsFromChart(chart);
  const canRenderChart = hasChartData(rows);

  return (
    <div className="erp-card p-5 flex flex-col min-w-0 overflow-visible">
      <h3 className="text-sm font-semibold text-foreground mb-1">{chart.titulo}</h3>
      <div className={CHART_WRAPPER_CLASS}>
        {canRenderChart ? (
          <BIStatusChart
            chart={chart}
            emptyTitle={emptyTitle}
            emptyMessage={emptyMessage}
            className="min-h-[280px] h-[320px] w-full min-w-0 aspect-auto"
          />
        ) : (
          <BIStatusChart
            chart={{ ...chart, dados: [] }}
            emptyTitle={emptyTitle}
            emptyMessage={emptyMessage}
            className="min-h-[280px] h-[320px] w-full min-w-0"
          />
        )}
      </div>
    </div>
  );
}
