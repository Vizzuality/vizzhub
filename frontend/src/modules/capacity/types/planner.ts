export interface PlannerRow {
  user_id: string;
  user_name: string;
  functional_area: string;
  project_id: string;
  project_name: string;
  is_absence?: boolean;
  is_other?: boolean;
  cells: Record<string, number>;
  comments: Record<string, string>;
}

export interface PlannerGroup {
  id: string;
  name: string;
  functional_area?: string;
  rows: PlannerRow[];
}

export interface PlannerResponse {
  groups: PlannerGroup[];
  weeks: string[];
  warnings: string[];
}

export interface CellUpdate {
  project_id: string;
  user_id: string;
  week_start: string;
  percentage: number | null;
  comment?: string | null;
}

export interface UpdatedAtResponse {
  updated_at: string | null;
}

export interface PlannerSuggestion {
  project_id: string;
  project_name: string;
  percentage: number;
  is_absence: boolean;
}

export interface PlannerSuggestionsResponse {
  suggestions: PlannerSuggestion[];
  others_percentage: number | null;
}
