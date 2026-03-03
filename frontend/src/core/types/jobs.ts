import type { CaptureReport } from '@/types/metrics';

export type JobType = 'capture_history';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobResponse {
  id: string;
  type: JobType;
  status: JobStatus;
  name: string;
  progress: number;
  created_at: string;
}

export interface JobDetailResponse extends JobResponse {
  description: string | null;
  project_id: string | null;
  params: Record<string, unknown>;
  result: CaptureReport | null;
  progress_message: string | null;
  logs: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobSummaryResponse {
  id: string;
  type: JobType;
  status: JobStatus;
  name: string;
  progress: number;
  project_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface CreateCaptureHistoryJobRequest {
  project_id: string;
  from_year: number;
  from_month: number;
  to_year: number;
  to_month: number;
  force?: boolean;
}
