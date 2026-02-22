# ISO Phase 9: Frontend — Snapshot + Review UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the snapshot list page (with capture button), review list page, and review detail page (with diff table, action forms, and sign-off flow).

**Architecture:** Replace placeholder pages with full implementations using existing hooks (`useIso.ts`), types (`iso.ts`), and API client. Follow existing table/badge/dialog patterns. Review detail is a new route `/iso/reviews/:id`. All filter state in URL via `useUrlState`.

**Tech Stack:** React, TypeScript, TanStack Query, shadcn/ui (Card, Badge, Button, Select, AlertDialog, Textarea, Label), Tailwind CSS, lucide-react icons, react-router-dom

---

### Task 1: Implement snapshot list page with capture button

**Files:**
- Modify: `frontend/src/pages/ISOSnapshots.tsx`

**Step 1: Implement the snapshot list page**

Replace the placeholder in `frontend/src/pages/ISOSnapshots.tsx` with a full implementation:

```typescript
import { useState } from 'react';
import { useIsoSnapshots, useCaptureSnapshot } from '@/hooks/useIso';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { formatDate } from '@/utils/formatters';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';

export default function ISOSnapshots(): JSX.Element {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useIsoSnapshots({ page, page_size: 20 });
  const capture = useCaptureSnapshot();

  const handleCapture = (): void => {
    capture.mutate();
  };

  return (
    <div className="space-y-4">
      {/* Header row with capture button and last capture date */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {data?.items?.[0] && (
            <>Last capture: {formatDate(data.items[0].captured_at)}</>
          )}
        </div>
        <Button onClick={handleCapture} disabled={capture.isPending}>
          <RefreshCw className={`mr-2 h-4 w-4 ${capture.isPending ? 'animate-spin' : ''}`} />
          {capture.isPending ? 'Capturing...' : 'Capture Snapshot'}
        </Button>
      </div>

      {/* Error banner */}
      {capture.isError && (
        <div className="rounded-lg border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          Capture failed: {capture.error?.message || 'Unknown error'}
        </div>
      )}

      {/* Loading state */}
      {isLoading && !data && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="pt-6 text-center text-sm text-muted-foreground">
            No snapshots yet. Click "Capture Snapshot" to take the first one.
          </CardContent>
        </Card>
      )}

      {/* Table */}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-muted-foreground border-b bg-muted/50">
                <th className="px-4 py-3 font-medium">Captured</th>
                <th className="px-4 py-3 font-medium">Provider</th>
                <th className="px-4 py-3 font-medium">Users</th>
                <th className="px-4 py-3 font-medium">Admins</th>
                <th className="px-4 py-3 font-medium">Groups</th>
                <th className="px-4 py-3 font-medium">External</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((snap) => {
                const s = snap.summary as Record<string, number>;
                return (
                  <tr key={snap.id} className="border-b last:border-b-0 hover:bg-muted/30">
                    <td className="px-4 py-3 text-sm">{formatDate(snap.captured_at)}</td>
                    <td className="px-4 py-3 text-sm">
                      <Badge variant="outline">{snap.provider}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm">{s.total_users ?? '-'}</td>
                    <td className="px-4 py-3 text-sm">{s.total_admins ?? '-'}</td>
                    <td className="px-4 py-3 text-sm">{s.total_groups ?? '-'}</td>
                    <td className="px-4 py-3 text-sm">{s.external_members ?? '-'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {data.total} snapshot{data.total !== 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">Page {page} of {data.pages}</span>
            <Button variant="outline" size="sm" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/ISOSnapshots.tsx
git commit -m "feat(iso-fe): implement snapshot list page with capture button"
```

---

### Task 2: Implement review list page with status filter

**Files:**
- Modify: `frontend/src/pages/ISOReviews.tsx`

**Step 1: Implement the review list page**

Replace the placeholder in `frontend/src/pages/ISOReviews.tsx`:

```typescript
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useIsoReviews } from '@/hooks/useIso';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { formatDate } from '@/utils/formatters';
import { ChevronLeft, ChevronRight } from 'lucide-react';

function getStatusBadge(status: string): JSX.Element {
  const config: Record<string, { variant: 'default' | 'secondary' | 'outline'; label: string }> = {
    draft: { variant: 'secondary', label: 'Draft' },
    completed: { variant: 'outline', label: 'Completed' },
    signed: { variant: 'default', label: 'Signed' },
  };
  const { variant, label } = config[status] ?? { variant: 'outline', label: status };
  return <Badge variant={variant}>{label}</Badge>;
}

export default function ISOReviews(): JSX.Element {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const params = {
    page,
    page_size: 20,
    ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
  };
  const { data, isLoading } = useIsoReviews(params);

  const handleStatusChange = (value: string): void => {
    setStatusFilter(value);
    setPage(1);
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <Select value={statusFilter} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="signed">Signed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Loading */}
      {isLoading && !data && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      )}

      {/* Empty */}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="pt-6 text-center text-sm text-muted-foreground">
            No reviews found.
          </CardContent>
        </Card>
      )}

      {/* Table */}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-muted-foreground border-b bg-muted/50">
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Scope</th>
                <th className="px-4 py-3 font-medium">Changes</th>
                <th className="px-4 py-3 font-medium">Signed</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((review) => {
                const ds = review.diff_summary as Record<string, number> | null;
                return (
                  <tr key={review.id} className="border-b last:border-b-0 hover:bg-muted/30">
                    <td className="px-4 py-3 text-sm">{formatDate(review.created_at)}</td>
                    <td className="px-4 py-3 text-sm">{getStatusBadge(review.status)}</td>
                    <td className="px-4 py-3 text-sm">{review.scope}</td>
                    <td className="px-4 py-3 text-sm">{ds?.total_changes ?? 0}</td>
                    <td className="px-4 py-3 text-sm">{review.signed_at ? formatDate(review.signed_at) : '-'}</td>
                    <td className="px-4 py-3 text-sm">
                      <Link to={`/iso/reviews/${review.id}`}>
                        <Button variant="ghost" size="sm">View</Button>
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {data.total} review{data.total !== 1 ? 's' : ''}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">Page {page} of {data.pages}</span>
            <Button variant="outline" size="sm" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/ISOReviews.tsx
git commit -m "feat(iso-fe): implement review list page with status filter"
```

---

### Task 3: Create review detail page with diff table and action forms

**Files:**
- Create: `frontend/src/pages/ISOReviewDetail.tsx`
- Modify: `frontend/src/App.tsx` (add route)

**Step 1: Create the review detail page**

Create `frontend/src/pages/ISOReviewDetail.tsx`:

The page should have:

1. **Header**: Review status badge, scope, created/signed dates, back button
2. **Notes section**: Editable textarea, auto-saves on blur
3. **Reviewer selector**: Select dropdown using `useUsers()` hook
4. **Diff summary cards**: Small stat cards showing counts per change type
5. **Actions table**: Each action row shows subject, change type, previous/current values, and an inline form with:
   - `action_taken` select (accepted/removed/corrected/exception)
   - `justification` textarea
   - Save button per row
6. **Sign button**: AlertDialog confirmation, disabled if any action lacks `action_taken`

Key patterns:
- Use `useParams()` to get review ID
- Use `useIsoReview(id)` for data
- Use `useUpdateReview(id)` for notes/reviewer changes
- Use `useUpdateReviewAction(id)` for action updates
- Use `useSignReview(id)` for signing
- Use `useUsers()` for reviewer dropdown
- Back button navigates to `/iso/reviews`

Structure the component with sub-components for clarity:
- `ReviewHeader` section
- `DiffSummary` section
- `ActionRow` component (one per action)
- `SignSection` at the bottom

**Step 2: Add route in App.tsx**

Add `<Route path="reviews/:id" element={<ISOReviewDetail />} />` inside the `/iso` route group, in both route trees.

Import: `import ISOReviewDetail from './pages/ISOReviewDetail';`

**Step 3: Commit**

```bash
git add frontend/src/pages/ISOReviewDetail.tsx frontend/src/App.tsx
git commit -m "feat(iso-fe): add review detail page with diff table, action forms, and sign-off"
```

---

### Task 4: Run frontend build + lint + tests

**Step 1: Run lint**

Run: `cd /Volumes/Work/Dev/project-score-card/frontend && npm run lint`
Expected: no errors

**Step 2: Run build**

Run: `cd /Volumes/Work/Dev/project-score-card/frontend && npm run build`
Expected: compiles successfully

**Step 3: Run tests**

Run: `cd /Volumes/Work/Dev/project-score-card/frontend && npm test -- --run`
Expected: all existing tests pass

**Step 4: Fix any issues and commit**

```bash
git add -A && git commit -m "style: fix lint issues in ISO frontend UI"
```
