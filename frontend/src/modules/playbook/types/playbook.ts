import type { DocNode } from '@/shared/types/doc';

export type { ReorderItem, VersionListItem, VersionDetail } from '@/shared/types/doc';

export interface PlaybookNode extends DocNode {
  is_public: boolean;
}

export interface TreeNode extends PlaybookNode {
  children: TreeNode[];
}

export interface PageContent {
  node_id: string;
  title: string;
  content: string;
  version: number;
  is_public: boolean;
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
  is_public?: boolean;
  parent_id?: string | null;
}

export interface AssetStatus {
  available: boolean;
}

export interface PublishStatus {
  status: 'running' | 'completed' | 'failed';
  page_count: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}
