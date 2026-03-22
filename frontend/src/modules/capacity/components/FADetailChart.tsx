import { useCallback, useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  Customized,
  LabelList,
} from 'recharts';
import type { PeriodUserInsight } from '@/modules/capacity/types/capacity';
import { FA_ORDER } from '@/modules/capacity/utils/constants';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { ChartPagination, useChartPagination } from './ChartPagination';
import { GroupSeparators } from './GroupSeparators';
import { shortMonth } from '@/shared/constants/dates';

const USER_PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#ec4899', '#f97316', '#14b8a6', '#a855f7',
  '#84cc16', '#e11d48', '#0ea5e9', '#d946ef', '#eab308',
];

interface ChartDataPoint {
  month: string;
  [key: string]: number | string;
}

function transformDetailData(data: PeriodUserInsight[]): {
  chartData: ChartDataPoint[];
  userNames: string[];
} {
  const userNameSet = new Set<string>();
  const chartData = data.map((period) => {
    const point: ChartDataPoint = { month: shortMonth(`${period.period}-01`) };
    for (const user of period.users) {
      userNameSet.add(user.name);
      point[`${user.name}_projects`] = Math.round(user.billable_pct * 100);
      point[`${user.name}_others`] = Math.round((1 - user.billable_pct) * 100);
      point[`${user.name}_count`] = user.billable_project_count;
    }
    return point;
  });
  return { chartData, userNames: [...userNameSet].sort() };
}

function renderCountLabel(props: Record<string, unknown>): JSX.Element | null {
  const { x, y, width, value } = props as {
    x: number; y: number; width: number; value: number;
  };
  if (value == null) return null;
  return (
    <text
      x={x + width / 2}
      y={y - 8}
      textAnchor="middle"
      fontSize={10}
      className="fill-foreground"
    >
      {value}
    </text>
  );
}

interface FADetailChartProps {
  readonly data: PeriodUserInsight[];
  readonly fa: string;
  readonly onFAChange: (fa: string) => void;
  readonly startDate: string;
  readonly endDate: string;
  readonly onRangeChange: (start: string, end: string) => void;
}

export function FADetailChart({
  data,
  fa,
  onFAChange,
  startDate,
  endDate,
  onRangeChange,
}: FADetailChartProps): JSX.Element {
  const { chartData, userNames } = useMemo(() => transformDetailData(data), [data]);
  const [hoveredUser, setHoveredUser] = useState<string | null>(null);
  const handleLeave = useCallback(() => setHoveredUser(null), []);
  const [page, setPage] = useState(0);

  const { visible } = useChartPagination(chartData, page);

  const userColors = useMemo(() => {
    const map: Record<string, string> = {};
    userNames.forEach((name, i) => {
      map[name] = USER_PALETTE[i % USER_PALETTE.length];
    });
    return map;
  }, [userNames]);

  const controls = (
    <div className="flex items-center justify-between">
      <h2 className="text-lg font-medium">Project time by user</h2>
      <div className="flex items-center gap-4">
        <select
          value={fa}
          onChange={(e) => onFAChange(e.target.value)}
          className="flex rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {FA_ORDER.map((code) => (
            <option key={code} value={code}>{code}</option>
          ))}
        </select>
        <MonthRangePicker
          startDate={startDate}
          endDate={endDate}
          onChange={onRangeChange}
          idPrefix="detail-"
        />
      </div>
    </div>
  );

  if (chartData.length === 0) {
    return (
      <div className="space-y-4">
        {controls}
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          No data for the selected period
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {controls}

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {userNames.map((name) => (
          <div key={name} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: userColors[name] }}
            />
            <span>{name}</span>
          </div>
        ))}
      </div>

      <div className="relative">
        {hoveredUser && (
          <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded bg-muted px-3 py-1.5 text-sm font-medium text-foreground shadow">
            {hoveredUser}
          </div>
        )}

        <ResponsiveContainer width="100%" height={450}>
          <BarChart data={visible} barCategoryGap="15%" barGap={1} maxBarSize={60} margin={{ top: 16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <Customized component={GroupSeparators} />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 12 }}
            />
            {userNames.flatMap((name) => [
              <Bar
                key={`${name}_projects`}
                dataKey={`${name}_projects`}
                stackId={name}
                fill={userColors[name]}
                fillOpacity={1}
                onMouseEnter={() => setHoveredUser(name)}
                onMouseLeave={handleLeave}
              />,
              <Bar
                key={`${name}_others`}
                dataKey={`${name}_others`}
                stackId={name}
                fill={userColors[name]}
                fillOpacity={0.3}
                onMouseEnter={() => setHoveredUser(name)}
                onMouseLeave={handleLeave}
              >
                <LabelList
                  dataKey={`${name}_count`}
                  content={renderCountLabel}
                />
              </Bar>,
            ])}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ChartPagination data={chartData} page={page} onPageChange={setPage} />
    </div>
  );
}
