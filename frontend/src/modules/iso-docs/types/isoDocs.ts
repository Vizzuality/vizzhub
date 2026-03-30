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
