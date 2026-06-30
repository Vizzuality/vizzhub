export interface Client {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  project_count: number;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  name: string;
}

export interface ClientUpdate {
  name?: string;
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
