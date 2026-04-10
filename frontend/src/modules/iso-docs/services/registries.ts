import api from '@/core/services/client';
import type {
  RegistryType,
  RegistryTypeCreate,
  RegistryTypeUpdate,
  RegistryRow,
  RegistryRowCreate,
  RegistryRowUpdate,
  RegistryAttachment,
} from '../types/registry';

export const registriesApi = {
  listTypes: async (): Promise<RegistryType[]> => {
    const { data } = await api.get<RegistryType[]>('/iso-docs/registry-types');
    return data;
  },

  getType: async (id: string): Promise<RegistryType> => {
    const { data } = await api.get<RegistryType>(`/iso-docs/registry-types/${id}`);
    return data;
  },

  createType: async (body: RegistryTypeCreate): Promise<RegistryType> => {
    const { data } = await api.post<RegistryType>('/iso-docs/registry-types', body);
    return data;
  },

  updateType: async (id: string, body: RegistryTypeUpdate): Promise<RegistryType> => {
    const { data } = await api.patch<RegistryType>(`/iso-docs/registry-types/${id}`, body);
    return data;
  },

  deleteType: async (id: string): Promise<void> => {
    await api.delete(`/iso-docs/registry-types/${id}`);
  },

  updateColumnVisibility: async (
    id: string,
    hiddenColumns: string[],
  ): Promise<RegistryType> => {
    const { data } = await api.patch<RegistryType>(
      `/iso-docs/registry-types/${id}/column-visibility`,
      { hidden_columns: hiddenColumns },
    );
    return data;
  },

  listYears: async (nodeId: string): Promise<number[]> => {
    const { data } = await api.get<number[]>(`/iso-docs/registries/${nodeId}/years`);
    return data;
  },

  listRows: async (nodeId: string, year?: number): Promise<RegistryRow[]> => {
    const { data } = await api.get<RegistryRow[]>(`/iso-docs/registries/${nodeId}/rows`, {
      params: year != null ? { year } : undefined,
    });
    return data;
  },

  createRow: async (nodeId: string, body: RegistryRowCreate): Promise<RegistryRow> => {
    const { data } = await api.post<RegistryRow>(`/iso-docs/registries/${nodeId}/rows`, body);
    return data;
  },

  updateRow: async (nodeId: string, rowId: string, body: RegistryRowUpdate): Promise<RegistryRow> => {
    const { data } = await api.patch<RegistryRow>(`/iso-docs/registries/${nodeId}/rows/${rowId}`, body);
    return data;
  },

  deleteRow: async (nodeId: string, rowId: string): Promise<void> => {
    await api.delete(`/iso-docs/registries/${nodeId}/rows/${rowId}`);
  },

  reorderRows: async (nodeId: string, rowIds: string[]): Promise<void> => {
    await api.put(`/iso-docs/registries/${nodeId}/rows/reorder`, { row_ids: rowIds });
  },

  exportRegistry: async (nodeId: string, format: 'xlsx' | 'csv', year?: number): Promise<Blob> => {
    const params: Record<string, string | number> = { format };
    if (year != null) params.year = year;
    const { data } = await api.get(`/iso-docs/registries/${nodeId}/export`, {
      params,
      responseType: 'blob',
    });
    return data as Blob;
  },

  importCsv: async (nodeId: string, file: File, year?: number): Promise<{ imported: number }> => {
    const form = new FormData();
    form.append('file', file);
    const params: Record<string, number> = {};
    if (year != null) params.year = year;
    const { data } = await api.post(`/iso-docs/registries/${nodeId}/import`, form, {
      params,
      headers: { 'Content-Type': undefined },
    });
    return data as { imported: number };
  },

  copyYear: async (
    nodeId: string,
    sourceYear: number,
    targetYear: number,
  ): Promise<{ copied: number }> => {
    const { data } = await api.post(`/iso-docs/registries/${nodeId}/copy-year`, null, {
      params: { source_year: sourceYear, target_year: targetYear },
    });
    return data as { copied: number };
  },

  exportToDrive: async (nodeId: string, year?: number): Promise<{ drive_file_id: string }> => {
    const params: Record<string, number> = {};
    if (year != null) params.year = year;
    const { data } = await api.post(`/iso-docs/registries/${nodeId}/export-drive`, null, { params });
    return data as { drive_file_id: string };
  },

  uploadAttachment: async (
    nodeId: string,
    rowId: string,
    file: File,
    fieldKey?: string,
  ): Promise<RegistryAttachment> => {
    const form = new FormData();
    form.append('file', file);
    if (fieldKey) form.append('field_key', fieldKey);
    const { data } = await api.post<RegistryAttachment>(
      `/iso-docs/registries/${nodeId}/rows/${rowId}/attachments`,
      form,
      { headers: { 'Content-Type': undefined } },
    );
    return data;
  },

  deleteAttachment: async (attachmentId: string): Promise<void> => {
    await api.delete(`/iso-docs/registries/attachments/${attachmentId}`);
  },
};
