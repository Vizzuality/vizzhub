export interface ConfigParameter {
  name: string;
  value: string;
  unit?: string;
  notes?: string;
}

export interface ConfigSection {
  category: string;
  parameters: ConfigParameter[];
}

export interface ConfigResponse {
  targets: ConfigSection;
  global_weights: ConfigSection;
  constants: ConfigSection;
  time_weights: ConfigSection;
  cost_weights: ConfigSection;
  quality_weights: ConfigSection;
  value_weights: ConfigSection;
  satisfaction_weights: ConfigSection;
  flow_weights: ConfigSection;
  engineering_weights: ConfigSection;
  risk_weights: ConfigSection;
}
