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
  functional_area: string;
  avg_billable_projects: number;
  total_distinct_projects: number;
  segments: AllocationSegment[];
}

export interface AllocationUsersResponse {
  periods_used: string[];
  users: UserAllocation[];
}

export interface ProjectAllocationSegment {
  user_id: string;
  user_name: string;
  avg_percentage: number;
  months_active: string[];
}

export interface ProjectAllocation {
  project_id: string;
  name: string;
  avg_people: number;
  total_distinct_people: number;
  segments: ProjectAllocationSegment[];
}

export interface AllocationProjectsResponse {
  periods_used: string[];
  projects: ProjectAllocation[];
}
