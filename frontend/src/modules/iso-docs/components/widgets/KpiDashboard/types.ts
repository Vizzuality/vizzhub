import type { RegistryRow } from '../../../types/registry';

export interface IsoCycle {
  year: number;       // e.g. 2025 means March 2025 – February 2026
  startYear: number;  // 2025
  startMonth: number; // 3
  endYear: number;    // 2026
  endMonth: number;   // 2
}

export interface ScorecardRowDef {
  key: string;
  name: string;
  description: string;
  formula: string;
  level: 0 | 1 | 2;
  parentKey?: string;
  weight?: string;
}

export interface MonthColumn {
  year: number;
  month: number;
  label: string; // "Mar 2025"
}

export type ManualKpiRow = RegistryRow;

export interface ManualKpiData {
  name: string;
  scope: string;
  responsible: string;
  methodology: string;
  formula: string;
  target: number | null;
  periodicity: string;
  [monthKey: string]: unknown; // m03, m04, ..., m02
}
