import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { buildScorecardRows, GLOBAL_WEIGHT_KEYS, DIMENSION_DEFINITIONS } from './constants';
import { periodKey } from './useKpiDashboard';
import type { MonthColumn } from './types';
import type { GlobalMetricsRecord, ScoringConfig } from '@/modules/scorecard/types';

interface ScorecardTableProps {
  readonly months: MonthColumn[];
  readonly metricsByPeriod: Map<string, GlobalMetricsRecord>;
  readonly globalWeights: ScoringConfig['global_weights'];
  readonly targets: ScoringConfig['targets'];
}

function scoreColor(value: number | null, level: 0 | 1 | 2): string {
  if (value === null) return '';
  // Only apply traffic light to scores/dimensions (0-100 scale, already normalized)
  // Indicators (level 2) have mixed scales and directions — no generic coloring
  if (level === 2) return '';

  if (value >= 80) return 'text-green-600 dark:text-green-400';
  if (value >= 60) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function extractValue(
  record: GlobalMetricsRecord,
  key: string,
  level: 0 | 1 | 2,
): number | null {
  if (level === 0) {
    const s = record.scores.score;
    if (!s || s.count === 0) return null;
    return s.value !== null ? Math.round(s.value * 10) / 10 : null;
  }
  if (level === 1) {
    const scores = record.scores as unknown as Record<string, { value: number | null; count: number }>;
    const entry = scores[key];
    if (!entry || entry.count === 0) return null;
    return entry.value !== null ? Math.round(entry.value * 10) / 10 : null;
  }
  // level 2: indicators — check count to distinguish "no data" from "real zero"
  const indicators = record.indicators as unknown as Record<string, { value: number | null; count: number }>;
  const entry = indicators[key];
  if (!entry || entry.count === 0) return null;
  const v = entry.value;
  return v !== null ? Math.round(v * 10) / 10 : null;
}

function getWeight(
  key: string,
  level: 0 | 1 | 2,
  globalWeights: ScoringConfig['global_weights'],
): string {
  if (level !== 1) return '';
  const weightKey = GLOBAL_WEIGHT_KEYS[key];
  if (!weightKey) return '';
  const weights = globalWeights as Record<string, number>;
  const w = weights[weightKey];
  if (w === undefined) return '';
  return `${Math.round(w * 100)}%`;
}

function getTarget(
  key: string,
  level: 0 | 1 | 2,
  targets: ScoringConfig['targets'],
): string {
  if (level <= 1) return '80';
  const t = (targets as Record<string, number | undefined>)[key];
  if (t === undefined) return '';
  return String(t);
}

export function ScorecardTable({
  months,
  metricsByPeriod,
  globalWeights,
  targets,
}: ScorecardTableProps): React.ReactElement {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const allRows = buildScorecardRows();

  const visibleRows = allRows.filter((row) => {
    if (row.level !== 2) return true;
    return !collapsed.has(row.parentKey ?? '');
  });

  function toggleDimension(key: string): void {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  const dimensionKeys = new Set(DIMENSION_DEFINITIONS.map((d) => d.key));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b">
            <th
              className={cn(
                'sticky left-0 z-10 bg-background text-left px-3 py-2 font-semibold min-w-[220px]',
              )}
            >
              Name
            </th>
            <th className="text-left px-3 py-2 font-semibold min-w-[200px]">Description</th>
            <th className="text-left px-3 py-2 font-semibold min-w-[200px]">Formula</th>
            <th className="text-center px-3 py-2 font-semibold w-16">Target</th>
            <th className="text-center px-3 py-2 font-semibold w-16">Weight</th>
            {months.map((m) => (
              <th key={`${m.year}-${m.month}`} className="text-center px-2 py-2 font-semibold min-w-[64px]">
                {m.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => {
            const isDimension = dimensionKeys.has(row.key);
            const isCollapsed = collapsed.has(row.key);
            const rowKey = row.level === 2 ? `${row.parentKey}__${row.key}` : row.key;

            return (
              <tr
                key={rowKey}
                className={cn('border-b hover:bg-muted/20 transition-colors', {
                  'font-bold bg-muted/30': row.level === 0,
                  'font-semibold cursor-pointer': row.level === 1,
                })}
                onClick={isDimension ? () => toggleDimension(row.key) : undefined}
              >
                <td
                  className={cn(
                    'sticky left-0 z-10 bg-background px-3 py-2',
                    row.level === 0 && 'font-bold',
                    row.level === 2 && 'pl-8 text-muted-foreground',
                  )}
                >
                  <span className="flex items-center gap-1">
                    {isDimension && (
                      <span className="shrink-0">
                        {isCollapsed ? (
                          <ChevronRight className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </span>
                    )}
                    {row.name}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {row.description}
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {row.formula}
                </td>
                <td className="px-3 py-2 text-center">
                  {getTarget(row.key, row.level, targets)}
                </td>
                <td className="px-3 py-2 text-center">
                  {getWeight(row.key, row.level, globalWeights)}
                </td>
                {months.map((m) => {
                  const record = metricsByPeriod.get(periodKey(m.year, m.month));
                  const value = record ? extractValue(record, row.key, row.level) : null;
                  return (
                    <td
                      key={`${m.year}-${m.month}`}
                      className={cn(
                        'px-2 py-2 text-center tabular-nums',
                        value !== null && scoreColor(value, row.level),
                      )}
                    >
                      {value !== null ? value : '—'}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
