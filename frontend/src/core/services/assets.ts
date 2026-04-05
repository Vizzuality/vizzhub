import api from './client';

export interface Asset {
  id: string;
  filename: string;
  s3_key: string;
  url: string | null;
  content_type: string;
  size_bytes: number;
  uploaded_by_id: string | null;
  created_at: string;
  node_id: string | null;
  node_title: string | null;
  row_id: string;
  field_key: string | null;
}

export interface AssetListResponse {
  items: Asset[];
  total: number;
  page: number;
  page_size: number;
}

export const assetsApi = {
  list: async (params: {
    page?: number;
    page_size?: number;
    content_type?: string;
  }): Promise<AssetListResponse> => {
    const response = await api.get<AssetListResponse>('/admin/assets', { params });
    return response.data;
  },

  delete: async (assetId: string): Promise<void> => {
    await api.delete(`/admin/assets/${assetId}`);
  },
};
