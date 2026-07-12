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

export interface TermChip {
  term_id: string;
  taxonomy_id: string;
  taxonomy_slug: string;
  name: string;
  is_primary: boolean;
}

export interface ClientRef {
  id: string;
  name: string;
}

export interface ProjectIteration {
  id: string;
  name: string;
  status: string;
  start_year: number | null;
  end_year: number | null;
  has_scorecard: boolean;
  is_billable: boolean;
  is_absence: boolean;
  client_id: string | null;
  client_name: string | null;
}

export interface ProgramProfile {
  objective: string | null;
  short_description: string | null;
  web_copy: string | null;
  website_url: string | null;
  impact_story: string | null;
  main_partner: string | null;
  stage: string | null;
  on_website: boolean;
}

export interface ProgramSummary {
  id: string;
  name: string;
  profile: ProgramProfile | null;
  terms: TermChip[];
  clients: ClientRef[];
  projects: ProjectIteration[];
}

export interface ProgramIndexResponse {
  programs: ProgramSummary[];
  total: number;
  pages: number;
}

export interface ProgramIndexFilters {
  search?: string;
  term_ids?: string[];
  client_id?: string;
  stage?: string;
  page?: number;
  n?: number;
}

export interface ProgramProfileUpdate {
  objective?: string | null;
  short_description?: string | null;
  web_copy?: string | null;
  website_url?: string | null;
  impact_story?: string | null;
  main_partner?: string | null;
  stage?: string | null;
  on_website?: boolean;
}

export interface ProgramTermsUpdate {
  taxonomy_id: string;
  term_ids: string[];
  primary_term_id: string | null;
}

export interface ProgramOption {
  id: string;
  name: string;
}
