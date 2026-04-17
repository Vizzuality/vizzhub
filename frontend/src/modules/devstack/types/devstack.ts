export const ENTRY_TYPES = ['skill', 'command', 'plugin', 'config', 'agent'] as const;
export type EntryType = typeof ENTRY_TYPES[number];

export const INSTALL_METHODS = ['github', 'npm', 'claude_plugin'] as const;
export type InstallMethod = typeof INSTALL_METHODS[number];

export const ENTRY_ORIGINS = ['internal', 'external'] as const;
export type EntryOrigin = typeof ENTRY_ORIGINS[number];

export interface DevstackEntry {
  id: string;
  name: string;
  description: string;
  type: EntryType;
  install_method: InstallMethod;
  url: string | null;
  package: string | null;
  package_version: string | null;
  required: boolean;
  origin: EntryOrigin;
  tech: string[];
  active: boolean;
  github_sha: string | null;
  latest_package_version: string | null;
  featured: boolean;
  created_at: string;
  updated_at: string;
}

export interface DevstackEntryCreate {
  name: string;
  description: string;
  type: EntryType;
  install_method: InstallMethod;
  url?: string | null;
  package?: string | null;
  package_version?: string | null;
  latest_package_version?: string | null;
  required: boolean;
  origin: EntryOrigin;
  tech: string[];
  active: boolean;
  featured: boolean;
}

export type DevstackEntryUpdate = Partial<DevstackEntryCreate>;

export interface DevstackEntryListResponse {
  items: DevstackEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface DevstackEntryListParams {
  search?: string;
  type?: string;
  required?: boolean;
  active?: boolean;
  featured?: boolean;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export interface ShaRefreshResult {
  total: number;
  updated: number;
  unchanged: number;
  failed: number;
}
