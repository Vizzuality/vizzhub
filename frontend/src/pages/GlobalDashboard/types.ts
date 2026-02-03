export interface Period {
  year: number;
  month: number;
}

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

export interface HistoricalPoint {
  period: string;
  value: number | null;
}
