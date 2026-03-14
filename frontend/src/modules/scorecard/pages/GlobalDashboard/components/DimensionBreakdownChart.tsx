import { useMemo } from 'react';
import { formatPeriod } from '@/utils/formatters';
import DimensionBreakdownCard, {
  DIMENSION_KEYS,
  DIMENSION_LABELS,
  type RadarDataPoint,
  type TrendDataPoint,
} from '../../../components/DimensionChart/DimensionBreakdownCard';
import type { Dimension } from '../../../types';
import type { GlobalMetricsRecord } from '../../../types/global';

const NEUTRAL_SCORE = 0;

interface DimensionBreakdownChartProps {
  readonly metrics: GlobalMetricsRecord;
  readonly history?: GlobalMetricsRecord[];
  readonly visibleDimensions: Set<Dimension>;
  readonly onToggleDimension: (dimension: Dimension) => void;
}

export default function DimensionBreakdownChart({
  metrics,
  history,
  visibleDimensions,
  onToggleDimension,
}: DimensionBreakdownChartProps): JSX.Element {
  const radarData: RadarDataPoint[] = useMemo(() =>
    DIMENSION_KEYS.map((key) => {
      const scoreValue = metrics.scores[key];
      const value = scoreValue?.value;
      return {
        dimension: DIMENSION_LABELS[key],
        score: value === null ? NEUTRAL_SCORE : Math.round(value),
        isNeutral: value === null || scoreValue.count === 0,
        fullMark: 100,
      };
    }),
    [metrics],
  );

  const trendData: TrendDataPoint[] = useMemo(() => {
    if (!history || history.length < 2) return [];
    return history
      .slice()
      .reverse()
      .map((r) => ({
        period: formatPeriod(r.period_year, r.period_month),
        ...Object.fromEntries(
          DIMENSION_KEYS.map((key) => [
            key,
            r.scores[key].value === null ? 0 : Math.round(r.scores[key].value),
          ]),
        ),
      }));
  }, [history]);

  return (
    <DimensionBreakdownCard
      radarData={radarData}
      trendData={trendData}
      visibleDimensions={visibleDimensions}
      onToggleDimension={onToggleDimension}
    />
  );
}
