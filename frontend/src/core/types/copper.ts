export type CopperOpportunityGroup = 'pending_signature' | 'signed';

export interface CopperProjectRef {
  id: string;
  name: string;
}

export interface CopperNewClient {
  name: string;
  code: string | null;
  copper_company_id: number | null;
}

export interface CopperOpportunity {
  opportunity_id: number;
  name: string;
  group: CopperOpportunityGroup;
  stage_changed_on: string | null;
  company_name: string | null;
  code: string | null;
  currency: string | null;
  original_budget: number | null;
  start_date: string | null;
  end_date: string | null;
  client_id: string | null;
  client_name: string | null;
  new_client: CopperNewClient | null;
  linked_projects: CopperProjectRef[];
  suggestion: CopperProjectRef | null;
}
