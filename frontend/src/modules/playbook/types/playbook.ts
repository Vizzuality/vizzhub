export interface PlaybookNode {
  id: string;
  title: string;
  slug: string;
  type: 'page' | 'group';
  parent_id: string | null;
  position: number;
  is_public: boolean;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
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

export interface ReorderItem {
  id: string;
  parent_id: string | null;
  position: number;
}

export interface VersionListItem {
  version: number;
  created_by_id: string | null;
  created_by_name: string | null;
  created_at: string;
  lines_added: number;
  lines_removed: number;
}

export interface VersionDetail {
  node_id: string;
  content: string;
  version: number;
  created_by_id: string | null;
  created_at: string;
}

export interface AssetStatus {
  available: boolean;
}
