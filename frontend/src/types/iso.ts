export type { PaginatedResponse } from './common';

export interface DiffSummary {
  total_changes: number;
  new_user: number;
  removed_user: number;
  role_change: number;
  new_external: number;
  group_membership_change: number;
}

export interface SnapshotSummary {
  total_users: number;
  total_admins: number;
  total_groups: number;
  external_members: number;
}

export interface AccessSnapshot {
  id: string;
  provider: string;
  captured_at: string;
  captured_by: string | null;
  data_version: string;
  source_metadata: Record<string, unknown>;
  data: Record<string, unknown>;
  summary: SnapshotSummary;
  created_at: string;
}

export interface AccessSnapshotSummary {
  id: string;
  provider: string;
  captured_at: string;
  captured_by: string | null;
  data_version: string;
  summary: SnapshotSummary;
  created_at: string;
  review_status: 'draft' | 'completed' | 'signed' | null;
}

export interface AccessReview {
  id: string;
  snapshot_id: string;
  previous_snapshot_id: string | null;
  reviewer_id: string | null;
  status: 'draft' | 'completed' | 'signed';
  scope: string;
  diff_summary: DiffSummary | null;
  notes: string | null;
  signed_by: string | null;
  signed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessReviewAction {
  id: string;
  review_id: string;
  subject_type: 'user' | 'group';
  subject_id: string;
  subject_label: string | null;
  change_type: string;
  previous_value: Record<string, unknown> | null;
  current_value: Record<string, unknown> | null;
  action_taken: 'accepted' | 'removed' | 'corrected' | 'exception' | null;
  justification: string | null;
  approved_by: string | null;
  exception_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessReviewDetail extends AccessReview {
  actions: AccessReviewAction[];
}

export interface AccessReviewUpdate {
  notes?: string;
  reviewer_id?: string;
}

export interface AccessReviewActionUpdate {
  action_taken?: 'accepted' | 'removed' | 'corrected' | 'exception';
  justification?: string;
  approved_by?: string;
  exception_until?: string;
}

export interface ActionDecision {
  action_id: string;
  action_taken: 'accepted' | 'removed' | 'corrected' | 'exception';
  justification?: string;
  exception_until?: string;
}

export interface SignReviewPayload {
  notes?: string;
  actions?: ActionDecision[];
}

export interface IsoConfigStatus {
  connected: boolean;
  domain: string | null;
}
