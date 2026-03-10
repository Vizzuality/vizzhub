import { useMemo } from 'react';
import type { DimensionScores, MetricsWithScores, Dimension } from '../../types';
import { formatPeriod } from '@/utils/formatters';
import DimensionBreakdownCard, {
  DIMENSION_KEYS,
  DIMENSION_LABELS,
  type RadarDataPoint,
  type TrendDataPoint,
} from './DimensionBreakdownCard';

const NEUTRAL_SCORE = 0;

interface DimensionChartProps {
  readonly scores: DimensionScores;
  readonly snapshots?: MetricsWithScores[];
  readonly visibleDimensions?: Set<Dimension>;
  readonly onToggleDimension?: (dimension: Dimension) => void;
}

export default function DimensionChart({
  scores,
  snapshots,
  visibleDimensions,
  onToggleDimension,
}: DimensionChartProps): JSX.Element {
  const radarData: RadarDataPoint[] = useMemo(() =>
    DIMENSION_KEYS.map((key) => {
      const value = scores[key];
      return {
        dimension: DIMENSION_LABELS[key],
        score: value ?? NEUTRAL_SCORE,
        isNeutral: value === null,
        fullMark: 100,
      };
    }),
    [scores],
  );

  const trendData: TrendDataPoint[] = useMemo(() => {
    if (!snapshots || snapshots.length < 2) return [];
    return snapshots
      .slice()
      .reverse()
      .map((s) => ({
        period: formatPeriod(s.period_year, s.period_month),
        ...Object.fromEntries(
          Object.entries(s.scores.dimensions).map(([key, value]) => [key, value ?? 0]),
        ),
      }));
  }, [snapshots]);

  return (
    <DimensionBreakdownCard
      radarData={radarData}
      trendData={trendData}
      visibleDimensions={visibleDimensions}
      onToggleDimension={onToggleDimension}
    />
  );
}
