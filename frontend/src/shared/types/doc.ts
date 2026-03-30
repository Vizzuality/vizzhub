export interface DocNode {
  id: string;
  title: string;
  slug: string;
  type: 'page' | 'group';
  parent_id: string | null;
  position: number;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocTreeNode extends DocNode {
  children: DocTreeNode[];
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
