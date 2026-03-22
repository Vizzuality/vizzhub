import { useCallback, useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  LabelList,
} from 'recharts';
import type { PeriodUserInsight } from '@/modules/capacity/types/capacity';
import { FA_COLORS, FA_ORDER } from '@/modules/capacity/utils/constants';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { shortMonth } from '@/shared/constants/dates';

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

  const color = FA_COLORS[fa] ?? '#6b7280';

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

      <div className="relative cursor-pointer">
        {hoveredUser && (
          <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded bg-muted px-2 py-1 text-sm text-foreground">
            {hoveredUser}
          </div>
        )}

        <ResponsiveContainer width="100%" height={450}>
          <BarChart data={chartData} barCategoryGap="15%" barGap={1} maxBarSize={60}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
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
                fill={color}
                fillOpacity={1}
                onMouseEnter={() => setHoveredUser(name)}
                onMouseLeave={handleLeave}
              />,
              <Bar
                key={`${name}_others`}
                dataKey={`${name}_others`}
                stackId={name}
                fill={color}
                fillOpacity={0.3}
                onMouseEnter={() => setHoveredUser(name)}
                onMouseLeave={handleLeave}
              >
                <LabelList
                  dataKey={`${name}_count`}
                  position="top"
                  style={{ fontSize: 10, fill: 'currentColor' }}
                />
              </Bar>,
            ])}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
