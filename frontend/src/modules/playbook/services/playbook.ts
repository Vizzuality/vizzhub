import api from '@/core/services/client';
import type {
  TreeNode,
  PlaybookNode,
  PageContent,
  PageSaveRequest,
  PageSaveResponse,
  NodeCreateRequest,
  NodeUpdateRequest,
  ReorderItem,
  VersionListItem,
  VersionDetail,
  AssetStatus,
} from '../types/playbook';

export const playbookApi = {
  getTree: async (): Promise<TreeNode[]> => {
    const { data } = await api.get<TreeNode[]>('/playbook/tree');
    return data;
  },

  createNode: async (body: NodeCreateRequest): Promise<PlaybookNode> => {
    const { data } = await api.post<PlaybookNode>('/playbook/nodes', body);
    return data;
  },

  updateNode: async (id: string, body: NodeUpdateRequest): Promise<PlaybookNode> => {
    const { data } = await api.patch<PlaybookNode>(`/playbook/nodes/${id}`, body);
    return data;
  },

  deleteNode: async (id: string): Promise<{ deleted_count: number }> => {
    const { data } = await api.delete<{ deleted_count: number }>(`/playbook/nodes/${id}`);
    return data;
  },

  reorderNodes: async (items: ReorderItem[]): Promise<void> => {
    await api.put('/playbook/nodes/reorder', { items });
  },

  getPage: async (nodeId: string): Promise<PageContent> => {
    const { data } = await api.get<PageContent>(`/playbook/pages/${nodeId}`);
    return data;
  },

  savePage: async (nodeId: string, body: PageSaveRequest): Promise<PageSaveResponse> => {
    const { data } = await api.put<PageSaveResponse>(`/playbook/pages/${nodeId}`, body);
    return data;
  },

  listVersions: async (nodeId: string): Promise<VersionListItem[]> => {
    const { data } = await api.get<VersionListItem[]>(`/playbook/pages/${nodeId}/versions`);
    return data;
  },

  getVersion: async (nodeId: string, version: number): Promise<VersionDetail> => {
    const { data } = await api.get<VersionDetail>(`/playbook/pages/${nodeId}/versions/${version}`);
    return data;
  },

  getAssetStatus: async (): Promise<AssetStatus> => {
    const { data } = await api.get<AssetStatus>('/playbook/assets/status');
    return data;
  },
};
