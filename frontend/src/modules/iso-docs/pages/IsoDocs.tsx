import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, FileText, MoreHorizontal, Trash2, History, File, Folder, ArrowLeft, Pencil, Filter, Download, Printer } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useSidebar } from '@/shared/components/ui/sidebar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { DocTree } from '@/shared/components/doc/DocTree';
import { DocViewer } from '@/shared/components/doc/DocViewer';
import { DocEditor } from '@/shared/components/doc/DocEditor';
import { NodeForm } from '@/shared/components/doc/NodeForm';
import { VersionHistoryDialog } from '@/shared/components/doc/VersionHistoryDialog';
import {
  useIsoDocTree,
  useCreateIsoDocNode,
  useUpdateIsoDocNode,
  useDeleteIsoDocNode,
  useReorderIsoDocNodes,
} from '../hooks/useIsoDocTree';
import { useIsoDocPage, useSaveIsoDocPage } from '../hooks/useIsoDocPage';
import { useIsoDocVersions, useIsoDocVersion } from '../hooks/useIsoDocVersions';
import { useIsoDocMetadata, useUpdateIsoDocMetadata } from '../hooks/useIsoDocMetadata';
import { MetadataPanel } from '../components/MetadataPanel';
import { MetadataEditDialog } from '../components/MetadataEditDialog';
import { MetadataFilters } from '../components/MetadataFilters';
import { usePermission, Action } from '@/core/permissions';
import type { MetadataFilterParams } from '../types/isoDocs';
import type { DocTreeNode, ReorderItem } from '@/shared/types/doc';

function flattenTree(nodes: DocTreeNode[]): DocTreeNode[] {
  const result: DocTreeNode[] = [];
  for (const node of nodes) {
    result.push(node);
    if (node.children.length > 0) {
      result.push(...flattenTree(node.children));
    }
  }
  return result;
}

function buildSlugPaths(
  nodes: DocTreeNode[],
  parentPath = '',
  slugToId = new Map<string, string>(),
  idToSlug = new Map<string, string>(),
): { slugToId: Map<string, string>; idToSlug: Map<string, string> } {
  for (const node of nodes) {
    const path = parentPath ? `${parentPath}/${node.slug}` : node.slug;
    slugToId.set(path, node.id);
    idToSlug.set(node.id, path);
    if (node.children.length > 0) {
      buildSlugPaths(node.children, path, slugToId, idToSlug);
    }
  }
  return { slugToId, idToSlug };
}

function buildReorderItems(
  tree: DocTreeNode[],
  dragIds: string[],
  parentId: string | null,
  index: number,
): ReorderItem[] {
  const flat = flattenTree(tree);
  const siblings = flat.filter(
    (n) => n.parent_id === parentId && !dragIds.includes(n.id),
  );
  siblings.sort((a, b) => a.position - b.position);
  const dragged = flat.filter((n) => dragIds.includes(n.id));

  const reordered = [...siblings];
  reordered.splice(index, 0, ...dragged);

  return reordered.map((n, i) => ({
    id: n.id,
    parent_id: parentId,
    position: i,
  }));
}

function GroupChildren({
  nodes,
  onSelect,
}: Readonly<{
  nodes: DocTreeNode[];
  onSelect: (id: string) => void;
}>): JSX.Element {
  return (
    <div className="space-y-1">
      {nodes.map((child) => (
        <button
          key={child.id}
          className="flex items-center gap-2 w-full text-left px-3 py-2 rounded hover:bg-muted text-sm"
          onClick={() => onSelect(child.id)}
        >
          {child.type === 'group' ? (
            <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <File className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <span>{child.title}</span>
        </button>
      ))}
    </div>
  );
}

function TreeSidebar({
  tree,
  treeLoading,
  selectedId,
  isEditor,
  filtersOpen,
  filters,
  onSelect,
  onMove,
  onAdd,
  onToggleFilters,
  onFiltersChange,
}: Readonly<{
  tree: DocTreeNode[];
  treeLoading: boolean;
  selectedId: string | null;
  isEditor: boolean;
  filtersOpen: boolean;
  filters: MetadataFilterParams;
  onSelect: (id: string) => void;
  onMove: (args: { dragIds: string[]; parentId: string | null; index: number }) => void;
  onAdd: () => void;
  onToggleFilters: () => void;
  onFiltersChange: (filters: MetadataFilterParams) => void;
}>): JSX.Element {
  const hasActiveFilters = !!(filters.category || filters.status || filters.standard || filters.clause);

  function renderSidebarContent(): JSX.Element {
    if (filtersOpen) {
      return (
        <MetadataFilters
          filters={filters}
          onFiltersChange={onFiltersChange}
          onSelect={onSelect}
          onClose={onToggleFilters}
        />
      );
    }
    if (treeLoading) {
      return <p className="text-sm text-muted-foreground p-2">Loading...</p>;
    }
    if (tree.length > 0) {
      return (
        <DocTree
          data={tree}
          selectedId={selectedId}
          onSelect={onSelect}
          onMove={isEditor ? onMove : undefined}
        />
      );
    }
    return (
      <div className="text-center py-8 px-4">
        <p className="text-sm text-muted-foreground mb-3">No documents yet</p>
        {isEditor && <Button size="sm" onClick={onAdd}>Create your first document</Button>}
      </div>
    );
  }

  return (
    <div data-iso-tree-sidebar className={`w-full md:w-72 shrink-0 border-r flex flex-col ${selectedId ? 'hidden md:flex' : ''}`}>
      <div className="flex items-center justify-between p-3 border-b">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FileText className="h-4 w-4" />
          ISO Documentation
        </div>
        <div className="flex items-center gap-0.5">
          <Button
            variant={filtersOpen || hasActiveFilters ? 'secondary' : 'ghost'}
            size="icon"
            className="h-7 w-7 relative"
            onClick={onToggleFilters}
          >
            <Filter className="h-4 w-4" />
            {hasActiveFilters && !filtersOpen && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-primary" />
            )}
          </Button>
          {isEditor && !filtersOpen && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onAdd}>
              <Plus className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
      <div className="flex-1 min-h-0 p-2">{renderSidebarContent()}</div>
    </div>
  );
}

export default function IsoDocs(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const { setOpen } = useSidebar();
  const didCollapse = useRef(false);
  useEffect(() => {
    if (!didCollapse.current) {
      setOpen(false);
      didCollapse.current = true;
    }
  }, [setOpen]);
  const [editing, setEditing] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [metadataEditOpen, setMetadataEditOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [metadataFilters, setMetadataFilters] = useState<MetadataFilterParams>({});

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const canEditIsoDocs = usePermission(Action.ISO_DOCS_EDIT);
  const isAdmin = bypassAuth || canAdmin;
  const isEditor = canEditIsoDocs || isAdmin;

  const { data: tree = [], isLoading: treeLoading } = useIsoDocTree();

  const flat = useMemo(() => flattenTree(tree), [tree]);
  const { slugToId, idToSlug } = useMemo(() => buildSlugPaths(tree), [tree]);

  const pagePath = searchParams.get('page');
  const selectedId = pagePath ? (slugToId.get(pagePath) ?? null) : null;

  const { data: page } = useIsoDocPage(selectedId);
  const { data: metadata } = useIsoDocMetadata(selectedId);
  const createNode = useCreateIsoDocNode();
  const updateNode = useUpdateIsoDocNode();
  const deleteNode = useDeleteIsoDocNode();
  const reorder = useReorderIsoDocNodes();
  const savePage = useSaveIsoDocPage(selectedId ?? '');
  const updateMetadata = useUpdateIsoDocMetadata(selectedId ?? '');
  const selectedNode = useMemo(
    () => flat.find((n) => n.id === selectedId),
    [flat, selectedId],
  );
  const isPage = selectedNode?.type === 'page';

  const { data: versions } = useIsoDocVersions(historyOpen ? selectedId : null);
  const { data: versionDetail } = useIsoDocVersion(
    selectedVersion !== null ? selectedId : null,
    selectedVersion,
  );

  const fetchVersion = useCallback(
    (version: number) => {
      if (version !== selectedVersion) {
        setSelectedVersion(version);
        return undefined;
      }
      return versionDetail;
    },
    [selectedVersion, versionDetail],
  );

  const handleHistoryOpenChange = (v: boolean): void => {
    setHistoryOpen(v);
    if (!v) setSelectedVersion(null);
  };

  const handleInternalLink = useCallback(
    (href: string) => {
      const url = new URL(href, window.location.origin);
      const pagePath = url.searchParams.get('page');
      if (pagePath) {
        setSearchParams({ page: pagePath }, { replace: true });
        setEditing(false);
      }
    },
    [setSearchParams],
  );

  const handleSelect = useCallback(
    (id: string) => {
      const path = idToSlug.get(id);
      if (path) setSearchParams({ page: path }, { replace: true });
      setEditing(false);
    },
    [setSearchParams, idToSlug],
  );

  const handleMove = useCallback(
    ({ dragIds, parentId, index }: { dragIds: string[]; parentId: string | null; index: number }) => {
      const items = buildReorderItems(tree, dragIds, parentId, index);
      reorder.mutate(items);
    },
    [tree, reorder],
  );

  const handleSave = useCallback(
    (content: string) => {
      if (!page) return;
      savePage.mutate(
        { content, expected_version: page.version },
        {
          onSuccess: (result) => {
            setEditing(false);
            if (result.conflict) {
              alert('This page was edited by someone else. Your changes have been saved as the latest version.');
            }
          },
        },
      );
    },
    [page, savePage],
  );

  const handleCreateNode = useCallback(
    (title: string, type: 'page' | 'group') => {
      createNode.mutate(
        {
          title,
          type,
          parent_id: selectedNode?.type === 'group' ? selectedId : null,
        },
        {
          onSuccess: (node) => {
            setFormOpen(false);
            if (node.type === 'page') {
              const parentPath = selectedNode?.type === 'group' && selectedId
                ? idToSlug.get(selectedId)
                : undefined;
              const newPath = parentPath ? `${parentPath}/${node.slug}` : node.slug;
              setSearchParams({ page: newPath }, { replace: true });
            }
          },
        },
      );
    },
    [createNode, selectedId, selectedNode, setSearchParams, idToSlug],
  );

  const handleDelete = useCallback(() => {
    if (!selectedId) return;
    deleteNode.mutate(selectedId, {
      onSuccess: () => {
        setDeleteConfirmOpen(false);
        setSearchParams({}, { replace: true });
      },
    });
  }, [selectedId, deleteNode, setSearchParams]);

  const handleRenameOpen = useCallback(() => {
    if (selectedNode) {
      setRenameValue(selectedNode.title);
      setRenameOpen(true);
    }
  }, [selectedNode]);

  const handleRename = useCallback(() => {
    const trimmed = renameValue.trim();
    if (!selectedId || !trimmed || trimmed === selectedNode?.title) {
      setRenameOpen(false);
      return;
    }
    updateNode.mutate(
      { id: selectedId, data: { title: trimmed } },
      { onSuccess: () => setRenameOpen(false) },
    );
  }, [selectedId, selectedNode, renameValue, updateNode]);

  const handleRestore = useCallback(
    (content: string) => {
      if (!page || !selectedId) return;
      savePage.mutate(
        { content, expected_version: page.version },
        { onSuccess: () => { setHistoryOpen(false); } },
      );
    },
    [page, selectedId, savePage],
  );

  const handleExportMarkdown = useCallback(() => {
    if (!page || !selectedNode) return;
    const blob = new Blob([page.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedNode.slug}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [page, selectedNode]);

  const handlePrintPdf = useCallback(() => {
    const contentEl = document.querySelector('[data-iso-content]');
    if (!contentEl) return;
    const iframe = document.createElement('iframe');
    Object.assign(iframe.style, { position: 'fixed', left: '-9999px', width: '0', height: '0' });
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument;
    if (!doc) { document.body.removeChild(iframe); return; }
    const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]'))
      .map((el) => el.outerHTML)
      .join('\n');
    doc.open();
    doc.write(`<!DOCTYPE html>
<html><head><title>${selectedNode?.title ?? 'ISO Document'}</title>${styles}
<style>body { padding: 1cm; background: white !important; color: black !important; }
button, [data-iso-actions] { display: none !important; }
@page { margin: 1.5cm; }</style>
</head><body>${contentEl.innerHTML}</body></html>`);
    doc.close();
    setTimeout(() => {
      iframe.contentWindow?.focus();
      iframe.contentWindow?.print();
      setTimeout(() => document.body.removeChild(iframe), 1000);
    }, 500);
  }, [selectedNode]);

  const descendantCount = useMemo(() => {
    if (!selectedNode) return 0;
    const countChildren = (node: DocTreeNode): number =>
      node.children.reduce((sum, c) => sum + 1 + countChildren(c), 0);
    return countChildren(selectedNode);
  }, [selectedNode]);

  const itemWord = descendantCount === 1 ? 'item' : 'items';
  const deleteDescription = selectedNode?.type === 'group' && descendantCount > 0
    ? `This will also delete ${descendantCount} ${itemWord} inside this group. This action cannot be undone.`
    : 'This action cannot be undone.';

  return (
    <div className="flex h-[calc(100vh-3rem)]" data-iso-root>
      <TreeSidebar
        tree={tree}
        treeLoading={treeLoading}
        selectedId={selectedId}
        isEditor={isEditor}
        filtersOpen={filtersOpen}
        filters={metadataFilters}
        onSelect={handleSelect}
        onMove={handleMove}
        onAdd={() => setFormOpen(true)}
        onToggleFilters={() => setFiltersOpen((v) => !v)}
        onFiltersChange={setMetadataFilters}
      />

      <div data-iso-content className={`flex-1 min-h-0 flex flex-col p-6 ${editing ? '' : 'overflow-auto'} ${selectedId ? '' : 'hidden md:block'}`}>
        {renderContent()}
      </div>

      <NodeForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={handleCreateNode}
        isLoading={createNode.isPending}
        parentId={selectedNode?.type === 'group' ? selectedId : null}
        rootLabel="Add to ISO documentation"
      />

      {metadata && (
        <MetadataEditDialog
          open={metadataEditOpen}
          onOpenChange={setMetadataEditOpen}
          metadata={metadata}
          onSave={(data) => {
            updateMetadata.mutate(data, {
              onSuccess: () => setMetadataEditOpen(false),
            });
          }}
          isSaving={updateMetadata.isPending}
        />
      )}

      <VersionHistoryDialog
        open={historyOpen}
        onOpenChange={handleHistoryOpenChange}
        versions={versions}
        currentVersion={page?.version ?? 0}
        onRestore={handleRestore}
        isRestoring={savePage.isPending}
        fetchVersion={fetchVersion}
      />

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete &ldquo;{selectedNode?.title}&rdquo;?
            </AlertDialogTitle>
            <AlertDialogDescription>{deleteDescription}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                handleDelete();
              }}
            >
              {deleteNode.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); }}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)}>Cancel</Button>
            <Button
              onClick={handleRename}
              disabled={!renameValue.trim() || updateNode.isPending}
            >
              {updateNode.isPending ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );

  function renderContent(): JSX.Element {
    if (!selectedId) {
      return (
        <div className="flex flex-col items-center pt-[20vh] gap-2">
          <h1 className="text-2xl font-semibold">ISO Documentation</h1>
          <p className="text-muted-foreground">Select a document from the tree to start</p>
        </div>
      );
    }

    if (editing) {
      return (
        <DocEditor
          initialContent={page?.content ?? ''}
          onSave={handleSave}
          onCancel={() => setEditing(false)}
          isSaving={savePage.isPending}
        />
      );
    }

    return (
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 md:hidden"
              onClick={() => setSearchParams({}, { replace: true })}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <h1 className="text-2xl font-semibold">{selectedNode?.title}</h1>
          </div>
          <div data-iso-actions className="flex items-center gap-2">
            {isPage && isEditor && (
              <Button size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {isEditor && (
                  <DropdownMenuItem onClick={handleRenameOpen}>
                    <Pencil className="h-4 w-4 mr-2" />
                    Rename
                  </DropdownMenuItem>
                )}
                {isPage && isAdmin && (
                  <DropdownMenuItem onClick={() => setHistoryOpen(true)}>
                    <History className="h-4 w-4 mr-2" />
                    Version history
                  </DropdownMenuItem>
                )}
                {isPage && (
                  <>
                    {isEditor && <DropdownMenuSeparator />}
                    <DropdownMenuItem onClick={handleExportMarkdown}>
                      <Download className="h-4 w-4 mr-2" />
                      Export Markdown
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handlePrintPdf}>
                      <Printer className="h-4 w-4 mr-2" />
                      Print / Save as PDF
                    </DropdownMenuItem>
                  </>
                )}
                {isEditor && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeleteConfirmOpen(true)}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete {selectedNode?.type === 'group' ? 'group' : 'page'}
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        {isPage && (
          <div className="space-y-6">
            {metadata && (
              <MetadataPanel
                metadata={metadata}
                onEdit={isEditor ? () => setMetadataEditOpen(true) : undefined}
              />
            )}
            <DocViewer content={page?.content ?? ''} onInternalLink={handleInternalLink} />
          </div>
        )}
        {!isPage && selectedNode && (
          <GroupChildren nodes={selectedNode.children} onSelect={handleSelect} />
        )}
      </div>
    );
  }
}
