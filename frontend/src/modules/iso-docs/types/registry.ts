export interface FormulaSpec {
  operation: 'multiply' | 'sum';
  fields: string[];
}

export interface ConditionalFormatRange {
  min: number;
  max: number;
  color: string;
  label?: string;
}

export interface ColumnDef {
  key: string;
  label: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'select' | 'user' | 'computed' | 'attachment';
  required: boolean;
  options?: string[];
  option_colors?: Record<string, string>;
  width?: number;
  formula?: FormulaSpec;
  conditional_format?: ConditionalFormatRange[];
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
  node_id: string | null;
  field_key: string | null;
  filename: string;
  s3_key: string;
  url: string | null;
  content_type: string;
  size_bytes: number;
  uploaded_by_id: string | null;
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
