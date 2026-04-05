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

export interface S3Image {
  key: string;
  filename: string;
  url: string;
  size_bytes: number;
  last_modified: string;
}

export interface S3ImageListResponse {
  items: S3Image[];
  total: number;
  prefix: string;
}

export type ImageSource = 'playbook' | 'iso-docs';

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

  listImages: async (source: ImageSource): Promise<S3ImageListResponse> => {
    const response = await api.get<S3ImageListResponse>('/admin/assets/images', {
      params: { source },
    });
    return response.data;
  },

  deleteImage: async (key: string): Promise<void> => {
    await api.delete('/admin/assets/images', { params: { key } });
  },

  batchDeleteImages: async (keys: string[]): Promise<void> => {
    await api.post('/admin/assets/images/batch-delete', { keys });
  },
};
