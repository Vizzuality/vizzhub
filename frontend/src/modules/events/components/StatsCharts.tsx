import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { useTheme } from 'next-themes';
import { THEME_COLORS, ROLE_COLORS } from '../utils/constants';
import type { EventStats, StatGroup } from '../types/events';

function resolveColorMap(
  map: Record<string, { light: string; dark: string }>,
  isDark: boolean,
): Record<string, string> {
  const resolved: Record<string, string> = {};
  for (const [key, value] of Object.entries(map)) {
    resolved[key] = isDark ? value.dark : value.light;
  }
  return resolved;
}

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>): JSX.Element | null {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-card text-card-foreground shadow-md px-3 py-1.5 text-xs">
      <span className="font-medium">{label}</span>: {payload[0].value}
    </div>
  );
}

type StatsChartsProps = {
  readonly stats: EventStats;
};

const CHART_PALETTE_LIGHT = [
  '#2563eb', '#16a34a', '#ca8a04', '#dc2626', '#7c3aed',
  '#0891b2', '#ea580c', '#db2777', '#64748b', '#059669',
];
const CHART_PALETTE_DARK = [
  '#60a5fa', '#4ade80', '#facc15', '#f87171', '#a78bfa',
  '#22d3ee', '#fb923c', '#f472b6', '#94a3b8', '#34d399',
];

function formatCost(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function getBarColor(
  label: string,
  colorMap: Record<string, string>,
  index: number,
  isDark: boolean,
): string {
  const palette = isDark ? CHART_PALETTE_DARK : CHART_PALETTE_LIGHT;
  return colorMap[label] ?? palette[index % palette.length];
}

function HorizontalBarCard({
  title,
  data,
  colorMap,
  isDark,
}: {
  readonly title: string;
  readonly data: StatGroup[];
  readonly colorMap?: Record<string, string>;
  readonly isDark: boolean;
}): JSX.Element {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No data</p>
        </CardContent>
      </Card>
    );
  }

  const height = Math.max(data.length * 32 + 20, 120);
  const resolvedColorMap = colorMap ?? {};

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 12, bottom: 0, left: 0 }}
          >
            <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
            <YAxis
              dataKey="label"
              type="category"
              width={120}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: 'transparent' }}
              content={<ChartTooltip />}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={24}>
              {data.map((entry, i) => (
                <Cell
                  key={entry.label}
                  fill={getBarColor(entry.label, resolvedColorMap, i, isDark)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function StatsCharts({ stats }: StatsChartsProps): JSX.Element {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const themeColorMap = resolveColorMap(THEME_COLORS, isDark);

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Events</p>
            <p className="text-2xl font-semibold">{stats.total_events}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Attendees</p>
            <p className="text-2xl font-semibold">{stats.total_attendees}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Cost</p>
            <p className="text-2xl font-semibold">
              {formatCost(stats.total_cost)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Chart grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
        <HorizontalBarCard
          title="By Quarter"
          data={stats.by_quarter}
          isDark={isDark}
        />
        <HorizontalBarCard
          title="By Theme"
          data={stats.by_theme}
          colorMap={themeColorMap}
          isDark={isDark}
        />
        <HorizontalBarCard
          title="By Role"
          data={stats.by_role}
          colorMap={ROLE_COLORS}
          isDark={isDark}
        />
        <HorizontalBarCard
          title="By Functional Area"
          data={stats.by_fa}
          isDark={isDark}
        />
        <HorizontalBarCard
          title="By Country"
          data={stats.by_country}
          isDark={isDark}
        />
      </div>
    </div>
  );
}
