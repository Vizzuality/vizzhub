import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid,
  Customized,
} from 'recharts';
import { Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/shared/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import type { ChartDataPoint, PeriodProjectInsight, ReportableUser } from '@/modules/capacity/types/capacity';
import { ITEM_PALETTE, ABSENCE_COLOR } from '@/modules/capacity/utils/constants';
import { MonthRangePicker } from '@/modules/capacity/components/MonthRangePicker';
import { ChartPagination, useChartPagination } from './ChartPagination';
import { GroupSeparators } from './GroupSeparators';
import { shortMonth } from '@/shared/constants/dates';

const OTHERS_KEY = '_others';
const OTHERS_LABEL = 'Others';
const ABSENCE_KEY = '_absence';
const ABSENCE_LABEL = 'Absence';

function transformUserDetailData(data: PeriodProjectInsight[]): {
  chartData: ChartDataPoint[];
  projectNames: string[];
} {
  const projectNameSet = new Set<string>();
  for (const period of data) {
    for (const project of period.projects) {
      projectNameSet.add(project.name);
    }
  }
  const projectNames = [...projectNameSet].sort((a, b) => a.localeCompare(b));

  const chartData = data.map((period) => {
    const point: ChartDataPoint = { month: shortMonth(`${period.period}-01`) };
    let billableTotal = 0;
    for (const project of period.projects) {
      const pct = Math.round(project.percentage * 100);
      point[project.name] = pct;
      billableTotal += pct;
    }
    const absencePct = Math.round(period.absence_pct * 100);
    point[ABSENCE_KEY] = absencePct;
    point[OTHERS_KEY] = Math.max(0, 100 - billableTotal - absencePct);
    return point;
  });
  return { chartData, projectNames };
}

interface UserDetailChartProps {
  readonly data: PeriodProjectInsight[];
  readonly userId: string;
  readonly users: ReportableUser[];
  readonly onUserChange: (userId: string) => void;
  readonly startDate: string;
  readonly endDate: string;
  readonly onRangeChange: (start: string, end: string) => void;
}

export function UserDetailChart({
  data,
  userId,
  users,
  onUserChange,
  startDate,
  endDate,
  onRangeChange,
}: UserDetailChartProps): JSX.Element {
  const { chartData, projectNames } = useMemo(() => transformUserDetailData(data), [data]);
  const [hoverInfo, setHoverInfo] = useState<{ label: string; value: number } | null>(null);
  const handleLeave = useCallback(() => setHoverInfo(null), []);
  const [page, setPage] = useState(0);

  useEffect(() => setPage(0), [userId]);

  const { visible } = useChartPagination(chartData, page);

  const projectColors = useMemo(() => {
    const map: Record<string, string> = {};
    projectNames.forEach((name, i) => {
      map[name] = ITEM_PALETTE[i % ITEM_PALETTE.length];
    });
    return map;
  }, [projectNames]);

  const userName = useMemo(
    () => users.find((u) => u.id === userId)?.name ?? '',
    [users, userId],
  );

  const [comboOpen, setComboOpen] = useState(false);

  const controls = (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-medium">Allocation by project</h2>
        <Popover open={comboOpen} onOpenChange={setComboOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={comboOpen}
              className="w-[200px] justify-between font-normal"
            >
              <span className="truncate">
                {userName || 'Select user...'}
              </span>
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
            <Command>
              <CommandInput placeholder="Search users..." />
              <CommandList>
                <CommandEmpty>No user found.</CommandEmpty>
                <CommandGroup>
                  {users.map((u) => (
                    <CommandItem
                      key={u.id}
                      value={u.name}
                      onSelect={() => {
                        onUserChange(u.id);
                        setComboOpen(false);
                      }}
                    >
                      <Check
                        className={cn(
                          'mr-2 h-4 w-4',
                          userId === u.id ? 'opacity-100' : 'opacity-0',
                        )}
                      />
                      {u.name}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
      <MonthRangePicker
        startDate={startDate}
        endDate={endDate}
        onChange={onRangeChange}
        idPrefix="user-detail-"
      />
    </div>
  );

  if (!userId) {
    return (
      <div className="space-y-4">
        {controls}
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Select a user to view project breakdown
        </div>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="space-y-4">
        {controls}
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          No data for {userName} in the selected period
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {controls}

      <div className="flex flex-wrap items-center gap-4 text-sm">
        {projectNames.map((name) => (
          <div key={name} className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: projectColors[name] }}
            />
            <span>{name}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: ABSENCE_COLOR, opacity: 0.6 }}
          />
          <span>{ABSENCE_LABEL}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: '#6b7280', opacity: 0.3 }}
          />
          <span>{OTHERS_LABEL}</span>
        </div>
      </div>

      <div className="relative">
        {hoverInfo && (
          <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded bg-muted px-3 py-1.5 text-sm font-medium text-foreground shadow">
            {hoverInfo.label}: {hoverInfo.value}%
          </div>
        )}

        <ResponsiveContainer width="100%" height={450}>
          <BarChart data={visible} barCategoryGap="25%" maxBarSize={60} margin={{ top: 16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <Customized component={GroupSeparators} />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 12 }}
            />
            {projectNames.map((name) => (
              <Bar
                key={name}
                dataKey={name}
                stackId="user"
                fill={projectColors[name]}
                fillOpacity={1}
                onMouseEnter={(d) => setHoverInfo({ label: name, value: Number(d?.[name] ?? 0) })}
                onMouseLeave={handleLeave}
              />
            ))}
            <Bar
              dataKey={ABSENCE_KEY}
              stackId="user"
              fill={ABSENCE_COLOR}
              fillOpacity={0.6}
              onMouseEnter={(d) => setHoverInfo({ label: ABSENCE_LABEL, value: Number(d?.[ABSENCE_KEY] ?? 0) })}
              onMouseLeave={handleLeave}
            />
            <Bar
              dataKey={OTHERS_KEY}
              stackId="user"
              fill="#6b7280"
              fillOpacity={0.3}
              onMouseEnter={(d) => setHoverInfo({ label: OTHERS_LABEL, value: Number(d?.[OTHERS_KEY] ?? 0) })}
              onMouseLeave={handleLeave}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <ChartPagination data={chartData} page={page} onPageChange={setPage} />
    </div>
  );
}
