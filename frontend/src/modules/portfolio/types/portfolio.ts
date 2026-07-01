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

export interface YearVolume {
  year: number;
  count: number;
}

export interface ClientSpend {
  client_id: string;
  client_name: string;
  spend_eur: number;
  project_count: number;
}

export interface MarginSplit {
  gain: number;
  loss: number;
  no_data: number;
  avg_margin: number | null;
}

export interface TermCount {
  term_name: string;
  count: number;
}

export interface TermBreakdown {
  taxonomy_slug: string;
  taxonomy_name: string;
  terms: TermCount[];
}

export interface PortfolioKpis {
  project_count: number;
  total_spend_eur: number;
  client_count: number;
  avg_margin: number | null;
}

export interface PortfolioDashboardSummary {
  year: number | null;
  available_years: number[];
  kpis: PortfolioKpis;
  volume_by_year: YearVolume[];
  spend_by_client: ClientSpend[];
  margin_split: MarginSplit;
  breakdowns: TermBreakdown[];
}
