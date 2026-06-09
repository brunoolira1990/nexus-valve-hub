import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from 'recharts';
import type { BIChart } from '@/services/api/dashboard';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import { chartRowsFromChart, hasChartData } from '@/lib/biChartData';
import { BI_CHART_COLORS } from './biFormat';
import { BIEmptyChart } from './BIEmptyChart';
import { cn } from '@/lib/utils';

type BIStatusChartProps = {
  chart: BIChart;
  className?: string;
  emptyTitle?: string;
  emptyMessage?: string;
};

const DEFAULT_CHART_CLASS = 'min-h-[280px] h-[320px] w-full min-w-0 aspect-auto';

export function BIStatusChart({ chart, className, emptyTitle, emptyMessage }: BIStatusChartProps) {
  const rows = chartRowsFromChart(chart);

  if (!hasChartData(rows)) {
    return (
      <BIEmptyChart
        title={emptyTitle ?? 'Sem dados no período'}
        message={emptyMessage ?? `Não há dados para exibir em «${chart.titulo}».`}
      />
    );
  }

  const config = Object.fromEntries(
    rows.map((r, i) => [
      r.name,
      { label: r.name, color: BI_CHART_COLORS[i % BI_CHART_COLORS.length] },
    ]),
  );

  const heightClass = cn(DEFAULT_CHART_CLASS, className);

  if (chart.tipo === 'line') {
    return (
      <ChartContainer config={config} className={heightClass}>
        <LineChart data={rows} margin={{ top: 12, right: 12, left: 4, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} />
          <YAxis tickLine={false} axisLine={false} fontSize={11} width={40} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ChartContainer>
    );
  }

  if (chart.tipo === 'donut') {
    return (
      <ChartContainer config={config} className={heightClass}>
        <PieChart>
          <ChartTooltip content={<ChartTooltipContent />} />
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius={64} outerRadius={100} paddingAngle={2}>
            {rows.map((_, i) => (
              <Cell key={i} fill={BI_CHART_COLORS[i % BI_CHART_COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer config={config} className={heightClass}>
      <BarChart data={rows} margin={{ top: 12, right: 12, left: 4, bottom: 48 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="name"
          tickLine={false}
          axisLine={false}
          fontSize={10}
          interval={0}
          angle={-28}
          textAnchor="end"
          height={64}
        />
        <YAxis tickLine={false} axisLine={false} fontSize={11} width={40} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {rows.map((_, i) => (
            <Cell key={i} fill={BI_CHART_COLORS[i % BI_CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
