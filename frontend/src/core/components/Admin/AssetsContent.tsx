import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Image, Trash2, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react';
import { queryKeys } from '@/core/hooks/queryKeys';
import { assetsApi } from '@/core/services/assets';
import type { ImageSource } from '@/core/services/assets';
import { formatBytes } from '@/utils/formatters';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';

function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function AssetIcon({ contentType }: { readonly contentType: string }): JSX.Element {
  if (contentType.startsWith('image/')) return <Image className="h-4 w-4 text-blue-500" />;
  return <FileText className="h-4 w-4 text-muted-foreground" />;
}

function ImagePreview({ url, filename }: { readonly url: string; readonly filename: string }): JSX.Element {
  const [hovered, setHovered] = useState(false);
  return (
    <div className="relative" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <Image className="h-4 w-4 text-blue-500" />
      {hovered && (
        <div className="absolute z-50 left-6 top-0 p-1 bg-background border rounded-md shadow-lg">
          <img src={url} alt={filename} className="max-h-48 max-w-64 rounded" />
        </div>
      )}
    </div>
  );
}

function useSelection<T extends string>(allKeys: T[]): {
  selected: Set<T>;
  allSelected: boolean;
  toggleOne: (key: T) => void;
  toggleAll: () => void;
  clear: () => void;
} {
  const [selected, setSelected] = useState<Set<T>>(new Set());

  const allSelected = allKeys.length > 0 && allKeys.every((k) => selected.has(k));

  const toggleOne = useCallback((key: T): void => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, []);

  const toggleAll = useCallback((): void => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allKeys));
    }
  }, [allSelected, allKeys]);

  const clear = useCallback((): void => setSelected(new Set()), []);

  return { selected, allSelected, toggleOne, toggleAll, clear };
}

interface BatchDeleteDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly count: number;
  readonly isPending: boolean;
  readonly onConfirm: () => void;
  readonly entityName: string;
  readonly warningText: string;
}

function BatchDeleteDialog({
  open, onOpenChange, count, isPending, onConfirm, entityName, warningText,
}: BatchDeleteDialogProps): JSX.Element {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {count} {entityName}{count !== 1 ? 's' : ''}?</AlertDialogTitle>
          <AlertDialogDescription>{warningText}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={(e) => { e.preventDefault(); onConfirm(); }}
          >
            {isPending ? 'Deleting...' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

interface SelectionToolbarProps {
  readonly selectedCount: number;
  readonly totalCount: number;
  readonly entityName: string;
  readonly onDelete: () => void;
}

function SelectionToolbar({ selectedCount, totalCount, entityName, onDelete }: SelectionToolbarProps): JSX.Element {
  return (
    <div className="flex items-center justify-between mb-2">
      {selectedCount > 0 ? (
        <Button variant="destructive" size="sm" onClick={onDelete}>
          <Trash2 className="h-3.5 w-3.5 mr-1" />
          Delete {selectedCount} selected
        </Button>
      ) : <div />}
      <span className="text-sm text-muted-foreground">
        {totalCount} {entityName}{totalCount !== 1 ? 's' : ''}
      </span>
    </div>
  );
}

const PAGE_SIZE = 50;

function AttachmentsTab(): JSX.Element {
  const [page, setPage] = useState(1);
  const [showBatchConfirm, setShowBatchConfirm] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.assets.list({ page }),
    queryFn: () => assetsApi.list({ page, page_size: PAGE_SIZE }),
    staleTime: 0,
  });

  const itemIds = data?.items.map((a) => a.id) ?? [];
  const { selected, allSelected, toggleOne, toggleAll, clear } = useSelection(itemIds);

  const deleteMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      for (const id of ids) await assetsApi.delete(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.assets.all });
      queryClient.invalidateQueries({ queryKey: ['iso-docs', 'registry-rows'] });
      clear();
      setShowBatchConfirm(false);
    },
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  if (isLoading) return <LoadingSpinner />;

  if (!data?.items.length) {
    return <p className="text-sm text-muted-foreground text-center py-8">No attachments uploaded yet.</p>;
  }

  return (
    <>
      <SelectionToolbar
        selectedCount={selected.size}
        totalCount={data.total}
        entityName="file"
        onDelete={() => setShowBatchConfirm(true)}
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox checked={allSelected} onCheckedChange={toggleAll} />
            </TableHead>
            <TableHead className="w-10" />
            <TableHead>Filename</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Parent Document</TableHead>
            <TableHead>Uploaded</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((asset) => (
            <TableRow key={asset.id}>
              <TableCell>
                <Checkbox checked={selected.has(asset.id)} onCheckedChange={() => toggleOne(asset.id)} />
              </TableCell>
              <TableCell><AssetIcon contentType={asset.content_type} /></TableCell>
              <TableCell>
                {asset.url ? (
                  <a href={asset.url} target="_blank" rel="noopener noreferrer"
                    className="text-primary hover:underline inline-flex items-center gap-1">
                    <span className="truncate max-w-[250px]">{asset.filename}</span>
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                ) : (
                  <span className="truncate max-w-[250px]">{asset.filename}</span>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">{formatBytes(asset.size_bytes)}</TableCell>
              <TableCell>
                {asset.node_title
                  ? <span className="text-sm">{asset.node_title}</span>
                  : <span className="text-sm text-muted-foreground">-</span>}
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">{formatShortDate(asset.created_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <BatchDeleteDialog
        open={showBatchConfirm}
        onOpenChange={setShowBatchConfirm}
        count={selected.size}
        isPending={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate([...selected])}
        entityName="attachment"
        warningText="This will permanently delete the selected files from storage. Any registry cells referencing them will show empty fields."
      />
    </>
  );
}

function ImagesTab({ source }: { readonly source: ImageSource }): JSX.Element {
  const [showBatchConfirm, setShowBatchConfirm] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.assets.images(source),
    queryFn: () => assetsApi.listImages(source),
    staleTime: 0,
  });

  const itemKeys = data?.items.map((i) => i.key) ?? [];
  const { selected, allSelected, toggleOne, toggleAll, clear } = useSelection(itemKeys);

  const deleteMutation = useMutation({
    mutationFn: (keys: string[]) => assetsApi.batchDeleteImages(keys),
    onSuccess: () => {
      queryClient.refetchQueries({ queryKey: queryKeys.assets.images(source) });
      clear();
      setShowBatchConfirm(false);
    },
  });

  if (isLoading) return <LoadingSpinner />;

  if (!data?.items.length) {
    return <p className="text-sm text-muted-foreground text-center py-8">No images uploaded yet.</p>;
  }

  return (
    <>
      <SelectionToolbar
        selectedCount={selected.size}
        totalCount={data.total}
        entityName="image"
        onDelete={() => setShowBatchConfirm(true)}
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox checked={allSelected} onCheckedChange={toggleAll} />
            </TableHead>
            <TableHead className="w-10" />
            <TableHead>Filename</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Uploaded</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((img) => (
            <TableRow key={img.key}>
              <TableCell>
                <Checkbox checked={selected.has(img.key)} onCheckedChange={() => toggleOne(img.key)} />
              </TableCell>
              <TableCell>
                <ImagePreview url={img.url} filename={img.filename} />
              </TableCell>
              <TableCell>
                <a href={img.url} target="_blank" rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1">
                  <span className="truncate max-w-[300px]">{img.filename}</span>
                  <ExternalLink className="h-3 w-3 shrink-0" />
                </a>
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">{formatBytes(img.size_bytes)}</TableCell>
              <TableCell className="text-muted-foreground text-sm">{formatShortDate(img.last_modified)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <BatchDeleteDialog
        open={showBatchConfirm}
        onOpenChange={setShowBatchConfirm}
        count={selected.size}
        isPending={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate([...selected])}
        entityName="image"
        warningText="This will permanently delete the selected images from storage. Any pages referencing them will show broken links."
      />
    </>
  );
}

export function AssetsContent(): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Assets</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="attachments">
          <TabsList>
            <TabsTrigger value="attachments">Attachments</TabsTrigger>
            <TabsTrigger value="playbook">Playbook Images</TabsTrigger>
            <TabsTrigger value="iso-docs">ISO Docs Images</TabsTrigger>
          </TabsList>
          <TabsContent value="attachments">
            <AttachmentsTab />
          </TabsContent>
          <TabsContent value="playbook">
            <ImagesTab source="playbook" />
          </TabsContent>
          <TabsContent value="iso-docs">
            <ImagesTab source="iso-docs" />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
