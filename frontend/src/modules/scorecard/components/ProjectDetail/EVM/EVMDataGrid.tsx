import type { EVMData } from '@/modules/scorecard/types';
import { formatCurrency } from '@/shared/utils/evmCalculations';

interface EVMDataGridProps {
  readonly evmData: EVMData;
  readonly currency?: string;
}

type CostVarianceTone = 'red' | 'green' | 'muted';

interface DataItem {
  label: string;
  value: string;
  sub?: string;
  tone?: CostVarianceTone;
}

const TONE_VALUE_CLASS: Record<CostVarianceTone, string> = {
  red: 'text-score-red',
  green: 'text-score-green',
  muted: '',
};

interface CostVariance {
  value: number;
  pct: number;
  tone: CostVarianceTone;
}

/**
 * Cost Variance (EV − AC) and CV%, signed.
 *   EV  = percent_completed × budget_total
 *   CV  = EV − cost_to_date
 *   CV% = CV / budget_total
 *
 * Returns null when any of the inputs is missing or zero — we cannot
 * compute a meaningful variance without a budget or any reported
 * progress + cost.
 */
export function computeCostVariance(evmData: EVMData): CostVariance | null {
  const { budget_total, cost_to_date, percent_completed } = evmData;
  if (!budget_total || budget_total <= 0) return null;
  if (!cost_to_date || cost_to_date <= 0) return null;
  if (percent_completed == null) return null;
  const ev = percent_completed * budget_total;
  const cv = ev - cost_to_date;
  const pct = (cv / budget_total) * 100;
  let tone: CostVarianceTone = 'muted';
  if (Math.abs(pct) >= 0.5) tone = cv >= 0 ? 'green' : 'red';
  return { value: cv, pct, tone };
}

function formatSignedCurrency(value: number, currency?: string): string {
  const abs = formatCurrency(Math.abs(value), currency);
  const sign = value >= 0 ? '+' : '−';
  return `${sign}${abs}`;
}

function formatSignedPct(value: number): string {
  const sign = value >= 0 ? '+' : '−';
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

export default function EVMDataGrid({ evmData, currency }: EVMDataGridProps): JSX.Element {
  const cv = computeCostVariance(evmData);

  const items: DataItem[] = [
    { label: 'Total Budget', value: formatCurrency(evmData.budget_total, currency) },
    { label: 'Actual Cost', value: formatCurrency(evmData.cost_to_date, currency) },
    { label: 'Work Completed', value: `${(evmData.percent_completed * 100).toFixed(0)}%` },
    { label: 'Expected Progress', value: `${(evmData.percent_planned * 100).toFixed(0)}%` },
    {
      label: 'Cost Variance',
      value: cv ? formatSignedCurrency(cv.value, currency) : '—',
      sub: cv ? formatSignedPct(cv.pct) : undefined,
      tone: cv?.tone ?? 'muted',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {items.map((item) => (
        <div key={item.label} className="p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">{item.label}</p>
          <p
            className={`text-2xl font-semibold ${item.tone ? TONE_VALUE_CLASS[item.tone] : ''}`}
          >
            {item.value}
          </p>
          {item.sub && (
            <p className={`text-xs mt-0.5 ${item.tone ? TONE_VALUE_CLASS[item.tone] : 'text-muted-foreground'}`}>
              {item.sub}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
