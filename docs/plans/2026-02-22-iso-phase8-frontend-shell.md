# ISO Phase 8: Frontend — ISO Module Shell Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the frontend shell for the ISO module: types, API client, hooks, query keys, routing, navigation, and a config page for Google Workspace connection management.

**Architecture:** Follow existing codebase patterns — types in `src/types/`, API client in `src/services/api/`, hooks in `src/hooks/`, pages in `src/pages/`. ISO gets a tab-based layout page (like Admin) with nested routes. Navigation added to AppLayout for admin users.

**Tech Stack:** React, TypeScript, React Router, TanStack Query, shadcn/ui, Tailwind CSS, axios

---

### Task 1: Create TypeScript types for ISO module

**Files:**
- Create: `frontend/src/types/iso.ts`
- Modify: `frontend/src/types/index.ts`

**Step 1: Create ISO types file**

Create `frontend/src/types/iso.ts`:

```typescript
export interface AccessSnapshot {
  id: string;
  provider: string;
  captured_at: string;
  captured_by: string | null;
  data_version: string;
  source_metadata: Record<string, unknown>;
  data: Record<string, unknown>;
  summary: Record<string, unknown>;
  created_at: string;
}

export interface AccessSnapshotSummary {
  id: string;
  provider: string;
  captured_at: string;
  captured_by: string | null;
  data_version: string;
  summary: Record<string, unknown>;
  created_at: string;
}

export interface AccessReview {
  id: string;
  snapshot_id: string;
  previous_snapshot_id: string | null;
  reviewer_id: string | null;
  status: 'draft' | 'completed' | 'signed';
  scope: string;
  diff_summary: Record<string, unknown> | null;
  notes: string | null;
  signed_by: string | null;
  signed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessReviewAction {
  id: string;
  review_id: string;
  subject_type: 'user' | 'group';
  subject_id: string;
  subject_label: string | null;
  change_type: string;
  previous_value: Record<string, unknown> | null;
  current_value: Record<string, unknown> | null;
  action_taken: 'accepted' | 'removed' | 'corrected' | 'exception' | null;
  justification: string | null;
  approved_by: string | null;
  exception_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessReviewDetail extends AccessReview {
  actions: AccessReviewAction[];
}

export interface AccessReviewUpdate {
  notes?: string;
  reviewer_id?: string;
}

export interface AccessReviewActionUpdate {
  action_taken?: 'accepted' | 'removed' | 'corrected' | 'exception';
  justification?: string;
  approved_by?: string;
  exception_until?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface IsoConfigStatus {
  connected: boolean;
  provider: string;
  domain: string | null;
  last_token_refresh: string | null;
}
```

**Step 2: Export from types barrel**

Add to `frontend/src/types/index.ts`:

```typescript
// ISO types
export type {
  AccessSnapshot,
  AccessSnapshotSummary,
  AccessReview,
  AccessReviewAction,
  AccessReviewActionUpdate,
  AccessReviewDetail,
  AccessReviewUpdate,
  IsoConfigStatus,
  PaginatedResponse,
} from './iso';
```

**Step 3: Commit**

```bash
git add frontend/src/types/iso.ts frontend/src/types/index.ts
git commit -m "feat(iso-fe): add TypeScript types for ISO module"
```

---

### Task 2: Create API client and query keys

**Files:**
- Create: `frontend/src/services/api/iso.ts`
- Modify: `frontend/src/services/api.ts` (barrel export)
- Modify: `frontend/src/hooks/queryKeys.ts`

**Step 1: Create ISO API client**

Create `frontend/src/services/api/iso.ts`:

```typescript
import type {
  AccessReviewActionUpdate,
  AccessReviewDetail,
  AccessReviewUpdate,
  AccessSnapshot,
  AccessSnapshotSummary,
  AccessReview,
  IsoConfigStatus,
  PaginatedResponse,
} from '../../types';
import api from './client';

export const isoApi = {
  // Config
  getConfigStatus: async (): Promise<IsoConfigStatus> => {
    const response = await api.get<IsoConfigStatus>('/iso/config/google-workspace');
    return response.data;
  },

  disconnect: async (): Promise<void> => {
    await api.delete('/iso/config/google-workspace/disconnect');
  },

  // Snapshots
  captureSnapshot: async (): Promise<AccessSnapshot> => {
    const response = await api.post<AccessSnapshot>('/iso/snapshots/capture');
    return response.data;
  },

  listSnapshots: async (params?: {
    provider?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<AccessSnapshotSummary>> => {
    const response = await api.get<PaginatedResponse<AccessSnapshotSummary>>(
      '/iso/snapshots',
      { params },
    );
    return response.data;
  },

  getSnapshot: async (id: string): Promise<AccessSnapshot> => {
    const response = await api.get<AccessSnapshot>(`/iso/snapshots/${id}`);
    return response.data;
  },

  // Reviews
  listReviews: async (params?: {
    status?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<AccessReview>> => {
    const response = await api.get<PaginatedResponse<AccessReview>>(
      '/iso/reviews',
      { params },
    );
    return response.data;
  },

  getReview: async (id: string): Promise<AccessReviewDetail> => {
    const response = await api.get<AccessReviewDetail>(`/iso/reviews/${id}`);
    return response.data;
  },

  updateReview: async (
    id: string,
    data: AccessReviewUpdate,
  ): Promise<AccessReview> => {
    const response = await api.patch<AccessReview>(`/iso/reviews/${id}`, data);
    return response.data;
  },

  updateAction: async (
    reviewId: string,
    actionId: string,
    data: AccessReviewActionUpdate,
  ): Promise<void> => {
    await api.patch(`/iso/reviews/${reviewId}/actions/${actionId}`, data);
  },

  signReview: async (id: string): Promise<AccessReview> => {
    const response = await api.post<AccessReview>(`/iso/reviews/${id}/sign`);
    return response.data;
  },
};
```

**Step 2: Export from barrel**

Add to `frontend/src/services/api.ts`:

```typescript
export { isoApi } from './api/iso';
```

**Step 3: Add ISO query keys**

Add to `frontend/src/hooks/queryKeys.ts` (before the closing `} as const`):

```typescript
  iso: {
    config: ['iso', 'config'] as const,
    snapshots: {
      all: ['iso', 'snapshots'] as const,
      list: (params: { provider?: string; page?: number; page_size?: number }) =>
        ['iso', 'snapshots', 'list', params] as const,
      detail: (id: string) => ['iso', 'snapshots', id] as const,
    },
    reviews: {
      all: ['iso', 'reviews'] as const,
      list: (params: { status?: string; page?: number; page_size?: number }) =>
        ['iso', 'reviews', 'list', params] as const,
      detail: (id: string) => ['iso', 'reviews', id] as const,
    },
  },
```

**Step 4: Commit**

```bash
git add frontend/src/services/api/iso.ts frontend/src/services/api.ts frontend/src/hooks/queryKeys.ts
git commit -m "feat(iso-fe): add ISO API client and query keys"
```

---

### Task 3: Create React Query hooks

**Files:**
- Create: `frontend/src/hooks/useIso.ts`

**Step 1: Create hooks file**

Create `frontend/src/hooks/useIso.ts`:

```typescript
import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { isoApi } from '../services/api';
import type { AccessReviewActionUpdate, AccessReviewUpdate } from '../types';
import { queryKeys } from './queryKeys';

// Config
export function useIsoConfig() {
  return useQuery({
    queryKey: queryKeys.iso.config,
    queryFn: isoApi.getConfigStatus,
  });
}

export function useDisconnectGoogleWorkspace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: isoApi.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.config });
    },
  });
}

// Snapshots
export function useIsoSnapshots(params: {
  provider?: string;
  page?: number;
  page_size?: number;
} = {}) {
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

export function useCaptureSnapshot() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: isoApi.captureSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.snapshots.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.iso.reviews.all });
    },
  });
}

// Reviews
export function useIsoReviews(params: {
  status?: string;
  page?: number;
  page_size?: number;
} = {}) {
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
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useIso.ts
git commit -m "feat(iso-fe): add React Query hooks for ISO module"
```

---

### Task 4: Create ISO layout page with routing and navigation

**Files:**
- Create: `frontend/src/pages/ISO.tsx`
- Create: `frontend/src/pages/ISOConfig.tsx`
- Modify: `frontend/src/App.tsx` (add routes)
- Modify: `frontend/src/components/layout/AppLayout.tsx` (add nav link)

**Step 1: Create ISO layout page**

Create `frontend/src/pages/ISO.tsx`:

```typescript
import { NavLink, Outlet, Navigate, useMatch } from 'react-router-dom';
import { cn } from '@/lib/utils';

const TABS = [
  { to: 'snapshots', label: 'Snapshots' },
  { to: 'reviews', label: 'Reviews' },
  { to: 'config', label: 'Configuration' },
] as const;

export default function ISO(): JSX.Element {
  const isIndex = useMatch('/iso');

  if (isIndex) {
    return <Navigate to="snapshots" replace />;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">
        ISO Access Review
      </h1>

      <nav className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
        {TABS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                isActive
                  ? 'bg-background text-foreground shadow'
                  : 'hover:bg-background/50 hover:text-foreground',
              )
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
```

**Step 2: Create ISO Config page**

Create `frontend/src/pages/ISOConfig.tsx`:

```typescript
import { useIsoConfig, useDisconnectGoogleWorkspace } from '@/hooks/useIso';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function ISOConfig(): JSX.Element {
  const { data: config, isLoading } = useIsoConfig();
  const disconnect = useDisconnectGoogleWorkspace();

  const handleConnect = (): void => {
    const domain = prompt('Enter your Google Workspace domain (e.g., empresa.com):');
    if (!domain) return;
    window.location.href = `/api/iso/config/google-workspace/authorize?domain=${encodeURIComponent(domain)}`;
  };

  const handleDisconnect = (): void => {
    if (confirm('Disconnect Google Workspace? This will stop automated snapshot captures.')) {
      disconnect.mutate();
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading configuration...</div>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Google Workspace Connection</CardTitle>
          <CardDescription>
            Connect your Google Workspace admin account to enable automated
            access reviews.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">Status:</span>
            {config?.connected ? (
              <Badge variant="default">Connected</Badge>
            ) : (
              <Badge variant="secondary">Not connected</Badge>
            )}
          </div>

          {config?.connected && config.domain && (
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Domain:</span>
              <span className="text-sm text-muted-foreground">
                {config.domain}
              </span>
            </div>
          )}

          <div className="flex gap-2">
            {config?.connected ? (
              <Button
                variant="destructive"
                onClick={handleDisconnect}
                disabled={disconnect.isPending}
              >
                {disconnect.isPending ? 'Disconnecting...' : 'Disconnect'}
              </Button>
            ) : (
              <Button onClick={handleConnect}>
                Connect Google Workspace
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 3: Create placeholder pages for snapshots and reviews tabs**

Create `frontend/src/pages/ISOSnapshots.tsx`:

```typescript
export default function ISOSnapshots(): JSX.Element {
  return (
    <div className="text-muted-foreground">
      Snapshot list will be implemented in Phase 9.
    </div>
  );
}
```

Create `frontend/src/pages/ISOReviews.tsx`:

```typescript
export default function ISOReviews(): JSX.Element {
  return (
    <div className="text-muted-foreground">
      Review list will be implemented in Phase 9.
    </div>
  );
}
```

**Step 4: Add ISO routes to App.tsx**

In `frontend/src/App.tsx`, add imports and routes. Add after AdminRoute block in both BYPASS_AUTH and normal route trees:

```typescript
import ISO from './pages/ISO';
import ISOConfig from './pages/ISOConfig';
import ISOSnapshots from './pages/ISOSnapshots';
import ISOReviews from './pages/ISOReviews';
```

Add route block (inside both route trees, after the admin route block, still inside AppLayout):

```typescript
<Route path="/iso" element={<ISO />}>
  <Route path="snapshots" element={<ISOSnapshots />} />
  <Route path="reviews" element={<ISOReviews />} />
  <Route path="config" element={<ISOConfig />} />
</Route>
```

**Step 5: Add ISO nav link to AppLayout**

In `frontend/src/components/layout/AppLayout.tsx`, add an "ISO" link after the Admin link in both desktop and mobile nav sections. Show it only for admin users:

Desktop nav (after the Admin link block):
```typescript
{isAdmin && (
  <Link to="/iso">
    <Button
      variant={location.pathname.startsWith('/iso') ? 'secondary' : 'ghost'}
    >
      ISO
    </Button>
  </Link>
)}
```

Mobile nav (after the Admin DropdownMenuItem):
```typescript
{isAdmin && (
  <DropdownMenuItem asChild>
    <Link to="/iso">ISO</Link>
  </DropdownMenuItem>
)}
```

**Step 6: Commit**

```bash
git add frontend/src/pages/ISO.tsx frontend/src/pages/ISOConfig.tsx frontend/src/pages/ISOSnapshots.tsx frontend/src/pages/ISOReviews.tsx frontend/src/App.tsx frontend/src/components/layout/AppLayout.tsx
git commit -m "feat(iso-fe): add ISO module shell with routing, nav, and config page"
```

---

### Task 5: Run frontend tests + lint

**Step 1: Run frontend tests**

Run: `cd /Volumes/Work/Dev/project-score-card/frontend && npm test -- --run`
Expected: all tests pass

**Step 2: Run linters**

Run: `cd /Volumes/Work/Dev/project-score-card/frontend && npm run lint`
Expected: no errors

**Step 3: Run build**

Run: `cd /Volumes/Work/Dev/project-score-card/frontend && npm run build`
Expected: builds successfully

**Step 4: Fix any issues and commit**

```bash
git add -A && git commit -m "style: fix lint issues in ISO frontend shell"
```
