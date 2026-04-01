export interface ColumnDef {
  key: string;
  label: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'select' | 'user';
  required: boolean;
  options?: string[];
  width?: number;
}

export interface RegistryType {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_yearly: boolean;
  schema: ColumnDef[];
  created_at: string;
  updated_at: string;
}

export interface RegistryTypeCreate {
  name: string;
  description?: string | null;
  is_yearly?: boolean;
  schema: ColumnDef[];
}

export interface RegistryTypeUpdate {
  name?: string;
  description?: string | null;
  is_yearly?: boolean;
  schema?: ColumnDef[];
}

export interface RegistryAttachment {
  id: string;
  row_id: string;
  field_key: string | null;
  filename: string;
  s3_key: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface RegistryRow {
  id: string;
  node_id: string;
  year: number | null;
  row_index: number;
  data: Record<string, unknown>;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
  attachments: RegistryAttachment[];
}

export interface RegistryRowCreate {
  year?: number | null;
  data: Record<string, unknown>;
}

export interface RegistryRowUpdate {
  data: Record<string, unknown>;
}
