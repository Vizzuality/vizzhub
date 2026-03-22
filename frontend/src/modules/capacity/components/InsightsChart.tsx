import { useCallback, useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import type { PeriodInsight } from '@/modules/capacity/types/capacity';
import { FA_COLORS, FA_ORDER } from '@/modules/capacity/utils/constants';
import { shortMonth } from '@/shared/constants/dates';
const BAR_TYPES = [
  { suffix: 'projects', opacity: 1 },
  { suffix: 'others', opacity: 0.3 },
] as const;

interface ChartDataPoint {
  month: string;
  [key: string]: number | string;
}

function transformData(data: PeriodInsight[]): ChartDataPoint[] {
  return data.map((period) => {
    const point: ChartDataPoint = {
      month: shortMonth(`${period.period}-01`),
      period: period.period,
    };
    for (const fa of period.functional_areas) {
      point[`${fa.short}_projects`] = Math.round(fa.billable_pct * 100);
      point[`${fa.short}_others`] = Math.round((1 - fa.billable_pct) * 100);
    }
    return point;
  });
}

interface InsightsChartProps {
  readonly data: PeriodInsight[];
  readonly onBarClick?: (fa: string, period: string) => void;
}

export function InsightsChart({ data, onBarClick }: InsightsChartProps): JSX.Element {
  const chartData = useMemo(() => transformData(data), [data]);
  const [hoveredFA, setHoveredFA] = useState<string | null>(null);

  const activeFAs = useMemo(() => {
    const found = new Set<string>();
    for (const period of data) {
      for (const fa of period.functional_areas) {
        found.add(fa.short);
      }
    }
    return FA_ORDER.filter((fa) => found.has(fa));
  }, [data]);

  const handleLeave = useCallback(() => setHoveredFA(null), []);

  if (chartData.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        No data for the selected period
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium">Project time per functional area</h2>

      <div className="flex items-center gap-4 text-sm">
        {activeFAs.map((fa) => (
          <div key={fa} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: FA_COLORS[fa] }}
            />
            <span>{fa}</span>
          </div>
        ))}
      </div>

      <div className="relative cursor-pointer">
        {hoveredFA && (
          <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded bg-muted px-2 py-1 text-sm text-foreground">
            {hoveredFA}
          </div>
        )}

        <ResponsiveContainer width="100%" height={450}>
          <BarChart data={chartData} barCategoryGap="15%" barGap={1}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 12 }}
            />
            {BAR_TYPES.flatMap(({ suffix, opacity }) =>
              activeFAs.map((fa) => (
                <Bar
                  key={`${fa}_${suffix}`}
                  dataKey={`${fa}_${suffix}`}
                  stackId={fa}
                  fill={FA_COLORS[fa]}
                  fillOpacity={opacity}
                  onMouseEnter={() => setHoveredFA(fa)}
                  onMouseLeave={handleLeave}
                  onClick={(barData) => {
                    if (onBarClick && barData?.payload?.period) {
                      onBarClick(fa, String(barData.payload.period));
                    }
                  }}
                />
              )),
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
