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
import type { ChartDataPoint, PeriodUserInsight } from '@/modules/capacity/types/capacity';
import { FA_ORDER, ITEM_PALETTE, ABSENCE_COLOR } from '@/modules/capacity/utils/constants';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { ChartPagination, useChartPagination } from './ChartPagination';
import { GroupSeparators } from './GroupSeparators';
import { shortMonth } from '@/shared/constants/dates';

function transformDetailData(data: PeriodUserInsight[]): {
  chartData: ChartDataPoint[];
  userNames: string[];
  userIdByName: Record<string, string>;
} {
  const userNameSet = new Set<string>();
  const userIdByName: Record<string, string> = {};
  for (const period of data) {
    for (const user of period.users) {
      userNameSet.add(user.name);
      userIdByName[user.name] = user.user_id;
    }
  }
  const userNames = [...userNameSet].sort((a, b) => a.localeCompare(b));

  const chartData = data.map((period) => {
    const point: ChartDataPoint = { month: shortMonth(`${period.period}-01`) };
    const presentUsers = new Set(period.users.map((u) => u.name));
    for (const user of period.users) {
      point[`${user.name}_projects`] = Math.round(user.billable_pct * 100);
      point[`${user.name}_absence`] = Math.round(user.absence_pct * 100);
      point[`${user.name}_others`] = Math.max(0, Math.round((1 - user.billable_pct - user.absence_pct) * 100));
      point[`${user.name}_count`] = user.billable_project_count;
    }
    for (const name of userNames) {
      if (!presentUsers.has(name)) {
        point[`${name}_empty`] = 100;
      }
    }
    return point;
  });
  return { chartData, userNames, userIdByName };
}

interface CountLabelProps {
  x?: string | number;
  y?: string | number;
  width?: string | number;
  value?: string | number;
}

function renderCountLabel({ x = 0, y = 0, width = 0, value }: CountLabelProps): JSX.Element | null {
  if (value == null) return null;
  const cx = Number(x) + Number(width) / 2;
  const cy = Number(y) - 8;
  return (
    <text
      x={cx}
      y={cy}
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
  readonly onUserClick?: (userId: string) => void;
}

export function FADetailChart({
  data,
  fa,
  onFAChange,
  startDate,
  endDate,
  onRangeChange,
  onUserClick,
}: FADetailChartProps): JSX.Element {
  const { chartData, userNames, userIdByName } = useMemo(() => transformDetailData(data), [data]);
  const [hoverInfo, setHoverInfo] = useState<{ label: string; value: number } | null>(null);
  const handleLeave = useCallback(() => setHoverInfo(null), []);
  const [page, setPage] = useState(0);

  const { visible } = useChartPagination(chartData, page);

  const userColors = useMemo(() => {
    const map: Record<string, string> = {};
    userNames.forEach((name, i) => {
      map[name] = ITEM_PALETTE[i % ITEM_PALETTE.length];
    });
    return map;
  }, [userNames]);

  const controls = (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-medium">Project time by user</h2>
        <select
          value={fa}
          onChange={(e) => onFAChange(e.target.value)}
          className="flex rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          {FA_ORDER.map((code) => (
            <option key={code} value={code}>{code}</option>
          ))}
        </select>
      </div>
      <MonthRangePicker
        startDate={startDate}
        endDate={endDate}
        onChange={onRangeChange}
        idPrefix="detail-"
      />
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
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: ABSENCE_COLOR, opacity: 0.6 }}
          />
          <span>Absence</span>
        </div>
      </div>

      <div className={`relative${onUserClick ? ' cursor-pointer' : ''}`}>
        {hoverInfo && (
          <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded bg-muted px-3 py-1.5 text-sm font-medium text-foreground shadow">
            {hoverInfo.label}: {hoverInfo.value}%
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
                key={`${name}_empty`}
                dataKey={`${name}_empty`}
                stackId={name}
                fill="#6b7280"
                fillOpacity={0.15}
              />,
              <Bar
                key={`${name}_projects`}
                dataKey={`${name}_projects`}
                stackId={name}
                fill={userColors[name]}
                fillOpacity={1}
                onMouseEnter={(d) => setHoverInfo({ label: `${name} — Projects`, value: Number(d?.[`${name}_projects`] ?? 0) })}
                onMouseLeave={handleLeave}
                onClick={() => {
                  if (onUserClick && userIdByName[name]) {
                    onUserClick(userIdByName[name]);
                  }
                }}
              />,
              <Bar
                key={`${name}_absence`}
                dataKey={`${name}_absence`}
                stackId={name}
                fill={ABSENCE_COLOR}
                fillOpacity={0.6}
                onMouseEnter={(d) => setHoverInfo({ label: `${name} — Absence`, value: Number(d?.[`${name}_absence`] ?? 0) })}
                onMouseLeave={handleLeave}
                onClick={() => {
                  if (onUserClick && userIdByName[name]) {
                    onUserClick(userIdByName[name]);
                  }
                }}
              />,
              <Bar
                key={`${name}_others`}
                dataKey={`${name}_others`}
                stackId={name}
                fill={userColors[name]}
                fillOpacity={0.3}
                onMouseEnter={(d) => setHoverInfo({ label: `${name} — Others`, value: Number(d?.[`${name}_others`] ?? 0) })}
                onMouseLeave={handleLeave}
                onClick={() => {
                  if (onUserClick && userIdByName[name]) {
                    onUserClick(userIdByName[name]);
                  }
                }}
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
