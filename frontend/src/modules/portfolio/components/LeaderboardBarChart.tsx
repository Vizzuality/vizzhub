import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { barColor, METRIC_CONFIG, type Metric } from '../utils/chart';

export interface BarDatum {
  readonly label: string;
  readonly value: number;
}

const ROW_HEIGHT = 44;
const LABEL_MAX = 30;
const AXIS_COLOR = 'var(--muted-foreground)';

function truncate(text: string): string {
  return text.length > LABEL_MAX ? `${text.slice(0, LABEL_MAX - 1)}…` : text;
}

interface TickProps {
  readonly x?: number;
  readonly y?: number;
  readonly payload?: { readonly value?: string };
}

function CategoryTick({ x, y, payload }: TickProps): JSX.Element {
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fontSize={12} fill={AXIS_COLOR}>
      {truncate(payload?.value ?? '')}
    </text>
  );
}

interface PlottedDatum extends BarDatum {
  readonly display: string;
}

interface TooltipRenderProps {
  readonly active?: boolean;
  readonly payload?: readonly { readonly payload?: PlottedDatum }[];
}

function LeaderboardTooltip({ active, payload }: TooltipRenderProps): JSX.Element | null {
  const datum = payload?.[0]?.payload;
  if (!active || !datum) return null;
  return (
    <div className="bg-popover border rounded-md px-3 py-2 shadow-lg text-xs">
      <div className="font-medium mb-0.5">{datum.label}</div>
      <div className="text-muted-foreground">{datum.display}</div>
    </div>
  );
}

export function LeaderboardBarChart({
  data,
  metric,
}: {
  readonly data: BarDatum[];
  readonly metric: Metric;
}): JSX.Element {
  if (data.length === 0) {
    return <p className="text-muted-foreground text-sm">No data for this view.</p>;
  }
  const cfg = METRIC_CONFIG[metric];
  const plotted: PlottedDatum[] = data.map((d) => ({ ...d, display: cfg.valueFormat(d.value) }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * ROW_HEIGHT)}>
      <BarChart data={plotted} layout="vertical" margin={{ top: 4, right: 20, bottom: 4, left: 8 }}>
        <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="var(--border)" opacity={0.6} />
        <XAxis
          type="number"
          tickFormatter={cfg.axisFormat}
          tick={{ fontSize: 12, fill: AXIS_COLOR }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          type="category"
          dataKey="label"
          width={196}
          tick={<CategoryTick />}
          tickLine={false}
          axisLine={false}
          interval={0}
        />
        <Tooltip cursor={false} content={<LeaderboardTooltip />} />
        <Bar dataKey="value" maxBarSize={26} radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {plotted.map((d) => (
            <Cell key={d.label} fill={barColor(d.value, metric)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
