export const ENTRY_TYPES = ['skill', 'command', 'plugin', 'config', 'agent'] as const;
export type EntryType = typeof ENTRY_TYPES[number];

export const INSTALL_METHODS = ['github', 'npm'] as const;
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
  required: boolean;
  origin: EntryOrigin;
  tech: string[];
  active: boolean;
}

export type DevstackEntryUpdate = Partial<DevstackEntryCreate>;

export interface DevstackEntryListResponse {
  items: DevstackEntry[];
  total: number;
}

export interface DevstackEntryListParams {
  type?: string;
  required?: boolean;
  active?: boolean;
}

export interface UserPref {
  entry_id: string;
  enabled: boolean;
  last_synced_sha: string | null;
  last_synced_at: string | null;
}
