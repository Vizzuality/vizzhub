import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { CHART_COLORS } from '../../utils/chartUtils';
import type { HistoricalDataPoint } from '../../types';

interface IndicatorChartProps {
  readonly data: HistoricalDataPoint[];
  readonly height: number;
  readonly chartMode: 'line' | 'bar';
  readonly chartColor: string;
  readonly target?: number | null;
  readonly lowerIsBetter: boolean;
  readonly indicatorSuffix: string;
}

export default function IndicatorChart({
  data,
  height,
  chartMode,
  chartColor,
  target,
  lowerIsBetter,
  indicatorSuffix,
}: IndicatorChartProps): JSX.Element {
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  const dataMin = values.length > 0 ? Math.min(...values) : 0;
  const dataMax = values.length > 0 ? Math.max(...values) : 100;
  const targetVal = target ?? (lowerIsBetter ? dataMax : dataMin);
  const padding = (dataMax - dataMin) * 0.1 || 10;
  const yMin = Math.floor(Math.min(dataMin, targetVal) - padding);
  const yMax = Math.ceil(Math.max(dataMax, targetVal) + padding);
  const domainMin = Math.max(0, yMin);
  const domainMax = yMax;

  const referenceAreas =
    target !== null &&
    target !== undefined &&
    (lowerIsBetter ? (
      <>
        <ReferenceArea y1={domainMin} y2={target} fill={CHART_COLORS.green} fillOpacity={0.1} />
        <ReferenceArea y1={target} y2={domainMax} fill={CHART_COLORS.red} fillOpacity={0.1} />
      </>
    ) : (
      <>
        <ReferenceArea y1={target} y2={domainMax} fill={CHART_COLORS.green} fillOpacity={0.1} />
        <ReferenceArea y1={domainMin} y2={target} fill={CHART_COLORS.red} fillOpacity={0.1} />
      </>
    ));

  const referenceLine = target !== null && target !== undefined && (
    <ReferenceLine
      y={target}
      stroke={CHART_COLORS.green}
      strokeWidth={2}
      strokeDasharray="4 2"
      label={{
        value: `KPI ${target}`,
        position: 'right',
        fontSize: 9,
        fill: CHART_COLORS.green,
      }}
    />
  );

  const tooltipContent = (props: {
    active?: boolean;
    payload?: Array<{ value?: unknown; payload?: { period: string } }>;
  }) => {
    const { active, payload } = props;
    if (active && payload?.length && payload[0]?.payload) {
      const point = payload[0];
      const value = point.value as number;
      return (
        <div className="bg-popover border rounded px-2 py-1 shadow-lg text-xs">
          <div className="font-medium">{point.payload?.period}</div>
          <div style={{ color: chartColor }}>
            {value?.toFixed(1)}
            {indicatorSuffix}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      {chartMode === 'line' ? (
        <LineChart data={data} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
          {referenceAreas}
          <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
          <YAxis
            domain={[domainMin, domainMax]}
            tick={{ fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={35}
            tickFormatter={(v) => `${v}`}
          />
          {referenceLine}
          <Tooltip content={tooltipContent} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={chartColor}
            strokeWidth={2}
            dot={{ r: 3, fill: chartColor }}
            connectNulls
          />
        </LineChart>
      ) : (
        <BarChart data={data} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
          {referenceAreas}
          <XAxis dataKey="period" tick={{ fontSize: 9 }} tickLine={false} axisLine={false} />
          <YAxis
            domain={[domainMin, domainMax]}
            tick={{ fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            width={35}
            tickFormatter={(v) => `${v}`}
          />
          {referenceLine}
          <Tooltip cursor={false} content={tooltipContent} />
          <Bar dataKey="value" fill={chartColor} radius={[4, 4, 0, 0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}
