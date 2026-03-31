import type { DocNode, DocTreeNode, ReorderItem, VersionListItem, VersionDetail } from '@/shared/types/doc';

export type { DocTreeNode as IsoDocTreeNode, ReorderItem, VersionListItem, VersionDetail };

export type IsoDocNode = DocNode;

export interface IsoDocPageContent {
  node_id: string;
  title: string;
  content: string;
  version: number;
  created_by_id: string | null;
  created_at: string;
}

export interface PageSaveRequest {
  content: string;
  expected_version: number;
}

export interface PageSaveResponse {
  node_id: string;
  version: number;
  conflict: boolean;
}

export interface NodeCreateRequest {
  title: string;
  type: 'page' | 'group';
  parent_id?: string | null;
}

export interface NodeUpdateRequest {
  title?: string;
  parent_id?: string | null;
}

export interface ChangelogEntry {
  version: string;
  date: string;
  author: string;
  description: string;
}

export interface IsoDocMetadata {
  id: string;
  node_id: string;
  code: string | null;
  standard: string[] | null;
  clauses: string[] | null;
  category: string | null;
  classification: string;
  doc_version: string | null;
  status: string | null;
  original_filename: string | null;
  changelog: ChangelogEntry[] | null;
  created_at: string;
  updated_at: string;
}

export interface MetadataUpdate {
  code?: string | null;
  standard?: string[] | null;
  clauses?: string[] | null;
  category?: string | null;
  classification?: string | null;
  doc_version?: string | null;
  status?: string | null;
  original_filename?: string | null;
  changelog?: ChangelogEntry[] | null;
}

export interface MetadataSearchResult {
  node_id: string;
  title: string;
  code: string | null;
  standard: string[] | null;
  clauses: string[] | null;
  category: string | null;
  status: string | null;
}

export interface TextSearchResult {
  node_id: string;
  title: string;
  snippet: string;
  code: string | null;
}

export interface MetadataFilterParams {
  category?: string;
  status?: string;
  standard?: string;
  clause?: string;
}

export const STATUS_LABELS: Record<string, string> = {
  approved: 'Approved',
  draft: 'Draft',
  under_review: 'Under Review',
};

export const CLASSIFICATION_LABELS: Record<string, string> = {
  internal_use: 'Internal use',
  confidential: 'Confidential',
};

export const CATEGORY_LABELS: Record<string, string> = {
  manual: 'Manual',
  policy: 'Policy',
  procedure: 'Procedure',
  plan: 'Plan',
  record: 'Record',
  report: 'Report',
};

export interface DriveExportStatus {
  connected: boolean;
  last_export_at: string | null;
  root_folder_id: string | null;
  exported_doc_count: number;
}

export interface DriveExportResponse {
  job_id: string;
}
