import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { isoApi } from '../services/api';
import type { SnapshotListParams, ReviewListParams } from '../services/api';
import type { AccessReviewActionUpdate, AccessReviewUpdate } from '../types';
import { queryKeys } from './queryKeys';

// --- Config ---

export function useIsoConfig() {
  return useQuery({
    queryKey: queryKeys.iso.config,
    queryFn: isoApi.getConfigStatus,
  });
}

export function useDisconnectGoogleWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => isoApi.disconnect(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.config });
    },
  });
}

// --- Snapshots ---

export function useIsoSnapshots(params: SnapshotListParams = {}) {
  return useQuery({
    queryKey: queryKeys.iso.snapshots.list(params),
    queryFn: () => isoApi.listSnapshots(params),
    placeholderData: keepPreviousData,
  });
}

export function useIsoSnapshot(id: string) {
  return useQuery({
    queryKey: queryKeys.iso.snapshots.detail(id),
    queryFn: () => isoApi.getSnapshot(id),
    enabled: !!id,
  });
}

export function useSnapshotReview(snapshotId: string) {
  return useQuery({
    queryKey: queryKeys.iso.reviews.bySnapshot(snapshotId),
    queryFn: () => isoApi.getSnapshotReview(snapshotId),
    enabled: !!snapshotId,
    retry: false,
  });
}

export function useCaptureSnapshot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => isoApi.captureSnapshot(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.snapshots.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.reviews.all });
    },
  });
}

// --- Reviews ---

export function useIsoReviews(params: ReviewListParams = {}) {
  return useQuery({
    queryKey: queryKeys.iso.reviews.list(params),
    queryFn: () => isoApi.listReviews(params),
    placeholderData: keepPreviousData,
  });
}

export function useIsoReview(id: string) {
  return useQuery({
    queryKey: queryKeys.iso.reviews.detail(id),
    queryFn: () => isoApi.getReview(id),
    enabled: !!id,
  });
}

export function useUpdateReview(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AccessReviewUpdate) => isoApi.updateReview(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.reviews.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.iso.reviews.detail(id),
      });
    },
  });
}

export function useUpdateReviewAction(reviewId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      actionId,
      data,
    }: {
      actionId: string;
      data: AccessReviewActionUpdate;
    }) => isoApi.updateAction(reviewId, actionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.iso.reviews.detail(reviewId),
      });
    },
  });
}

export function useSignReview(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => isoApi.signReview(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.reviews.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.iso.reviews.detail(id),
      });
    },
  });
}

export function useUnsignReview(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => isoApi.unsignReview(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.reviews.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.iso.reviews.detail(id),
      });
    },
  });
}
