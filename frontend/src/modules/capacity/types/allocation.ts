export interface AllocationSegment {
  project_id: string;
  project_name: string;
  avg_percentage: number;
  months_active: string[];
  type: 'billable' | 'absence' | 'other';
}

export interface UserAllocation {
  user_id: string;
  name: string;
  avg_billable_projects: number;
  total_distinct_projects: number;
  segments: AllocationSegment[];
}

export interface AllocationUsersResponse {
  periods_used: string[];
  users: UserAllocation[];
}
