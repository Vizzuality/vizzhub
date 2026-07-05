export interface ClientOption {
  id: string;
  name: string;
  code: string | null;
}

export interface Client {
  id: string;
  name: string;
  slug: string;
  code: string | null;
  primary_contact: string | null;
  is_active: boolean;
  project_count: number;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  name: string;
  code?: string | null;
  primary_contact?: string | null;
}

export interface ClientUpdate {
  name?: string;
  code?: string | null;
  primary_contact?: string | null;
  is_active?: boolean;
}

export interface ClientListParams {
  search?: string;
  page?: number;
  page_size?: number;
}

export interface ClientListResponse {
  items: Client[];
  total: number;
  page: number;
  page_size: number;
}

export interface MergeRequest {
  source_ids: string[];
}

export interface MergeResponse {
  merged_projects: number;
  target: Client;
}

export interface TaxonomyTerm {
  id: string;
  taxonomy_id: string;
  slug: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
}

export interface Taxonomy {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  cardinality: 'single' | 'multi';
  allows_primary: boolean;
  is_active: boolean;
  sort_order: number;
  terms: TaxonomyTerm[];
}

export interface ProjectRow {
  project_id: string;
  name: string;
  client_id: string | null;
  client_name: string | null;
  margin_pct: number;
  profit_eur: number | null;
  delay_months: number | null;
}

export interface ClientRow {
  client_id: string | null;
  client_name: string;
  project_count: number;
  profit_eur: number | null;
  margin_pct: number | null;
  delay_months: number | null;
}

export interface ProjectLeaderboard {
  available_years: number[];
  rows: ProjectRow[];
}

export interface ClientLeaderboard {
  available_years: number[];
  rows: ClientRow[];
}

export type ProgramAction = 'inherit' | 'link' | 'create' | 'none';

export interface OverviewUploadResult {
  batch_id: string;
  row_count: number;
  old_count: number;
}

export interface OverviewProjectCandidate {
  id: string;
  name: string;
  score: number;
}

export interface OverviewProgramCandidate {
  id: string;
  name: string;
  score: number;
}

export interface OverviewSuggestedProgram {
  program_id: string | null;
  score: number;
}

export interface OverviewImportProject {
  id: string;
  name: string;
  program_id: string | null;
}

export interface OverviewSuggestedProject {
  project_id: string | null;
  score: number;
}

export interface OverviewCurrentProgram {
  program_id: string | null;
  name: string | null;
}

export interface OverviewSavedDecision {
  project_id: string | null;
  program_action: ProgramAction | null;
  program_id: string | null;
  new_program_name: string | null;
}

export interface OverviewCurrentBatch {
  batch_id: string;
  row_count: number;
}

export interface OverviewDecisionPatch {
  project_id: string | null;
  program_action: ProgramAction;
  program_id: string | null;
  new_program_name: string | null;
}

export interface OverviewMatch {
  staging_id: string;
  name: string;
  is_old_project: boolean;
  client_type_raw: string | null;
  service_raw: string | null;
  impact_area_raw: string | null;
  suggested_project: OverviewSuggestedProject;
  project_candidates: OverviewProjectCandidate[];
  current_program: OverviewCurrentProgram;
  program_candidates: OverviewProgramCandidate[];
  suggested_program: OverviewSuggestedProgram;
  saved_decision: OverviewSavedDecision | null;
}

export interface OverviewDecision {
  staging_id: string;
  project_id: string | null;
  program_action: ProgramAction;
  program_id?: string | null;
  new_program_name?: string | null;
}

export interface OverviewApplyResult {
  applied: number;
  programs_created: number;
  programs_annotated: number;
  projects_linked_to_program: number;
  skipped: number;
  unmapped_terms: string[];
  unresolved_clients: string[];
}
