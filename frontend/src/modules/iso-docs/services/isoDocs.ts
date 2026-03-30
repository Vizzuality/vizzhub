import api from '@/core/services/client';
import type {
  IsoDocTreeNode,
  IsoDocNode,
  IsoDocPageContent,
  PageSaveRequest,
  PageSaveResponse,
  NodeCreateRequest,
  NodeUpdateRequest,
  ReorderItem,
  VersionListItem,
  VersionDetail,
  IsoDocMetadata,
  MetadataUpdate,
  MetadataSearchResult,
} from '../types/isoDocs';

export const isoDocsApi = {
  getTree: async (): Promise<IsoDocTreeNode[]> => {
    const { data } = await api.get<IsoDocTreeNode[]>('/iso-docs/tree');
    return data;
  },

  createNode: async (body: NodeCreateRequest): Promise<IsoDocNode> => {
    const { data } = await api.post<IsoDocNode>('/iso-docs/nodes', body);
    return data;
  },

  updateNode: async (id: string, body: NodeUpdateRequest): Promise<IsoDocNode> => {
    const { data } = await api.patch<IsoDocNode>(`/iso-docs/nodes/${id}`, body);
    return data;
  },

  deleteNode: async (id: string): Promise<{ deleted_count: number }> => {
    const { data } = await api.delete<{ deleted_count: number }>(`/iso-docs/nodes/${id}`);
    return data;
  },

  reorderNodes: async (items: ReorderItem[]): Promise<void> => {
    await api.put('/iso-docs/nodes/reorder', { items });
  },

  getPage: async (nodeId: string): Promise<IsoDocPageContent> => {
    const { data } = await api.get<IsoDocPageContent>(`/iso-docs/pages/${nodeId}`);
    return data;
  },

  savePage: async (nodeId: string, body: PageSaveRequest): Promise<PageSaveResponse> => {
    const { data } = await api.put<PageSaveResponse>(`/iso-docs/pages/${nodeId}`, body);
    return data;
  },

  listVersions: async (nodeId: string): Promise<VersionListItem[]> => {
    const { data } = await api.get<VersionListItem[]>(`/iso-docs/pages/${nodeId}/versions`);
    return data;
  },

  getVersion: async (nodeId: string, version: number): Promise<VersionDetail> => {
    const { data } = await api.get<VersionDetail>(`/iso-docs/pages/${nodeId}/versions/${version}`);
    return data;
  },

  getMetadata: async (nodeId: string): Promise<IsoDocMetadata> => {
    const { data } = await api.get<IsoDocMetadata>(`/iso-docs/pages/${nodeId}/metadata`);
    return data;
  },

  updateMetadata: async (nodeId: string, body: MetadataUpdate): Promise<IsoDocMetadata> => {
    const { data } = await api.put<IsoDocMetadata>(`/iso-docs/pages/${nodeId}/metadata`, body);
    return data;
  },

  searchMetadata: async (params: {
    standard?: string;
    category?: string;
    clause?: string;
    status?: string;
  }): Promise<MetadataSearchResult[]> => {
    const { data } = await api.get<MetadataSearchResult[]>('/iso-docs/metadata/search', { params });
    return data;
  },
};
