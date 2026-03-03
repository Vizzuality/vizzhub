export interface ConfigParameter {
  id: number;
  category: string;
  name: string;
  value: string;  // Decimal as string from API
  unit: string | null;
  notes: string | null;
}

export interface ConfigParameterUpdate {
  name: string;
  value: string;  // Decimal as string
  notes?: string | null;
}

export interface ValidationResponse {
  valid: boolean;
  errors: string[];
}
