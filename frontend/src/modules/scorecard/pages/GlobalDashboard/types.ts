export type { Period } from '@/utils/dateUtils';
export type { HistoricalDataPoint } from '@/modules/scorecard/types';

export interface TimelineDataPoint {
  readonly key: string;
  readonly label: string;
  readonly year: number;
  readonly month: number;
  readonly score: number | null;
  readonly hasData: boolean;
}

export interface MetricKPI {
  label: string;
  value: string | number | null;
}
