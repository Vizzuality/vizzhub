import { useState, useCallback, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, FileText, MoreHorizontal, Trash2, History, File, Folder, Table2, Blocks, ArrowLeft, Pencil, Filter, Download, Printer, Upload, Loader2, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
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
  AlertDialogTrigger,
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
import { RegistryView } from '../components/RegistryView';
import { isoDocsApi } from '../services/isoDocs';
import { RegistryTypePicker } from '../components/RegistryTypePicker';
import { WIDGET_REGISTRY } from '../components/widgets';
import { usePermission, Action } from '@/core/permissions';
import { useDriveExportStatus, useTriggerDriveExport } from '../hooks/useDriveExport';
import { useJobStatus } from '@/core/hooks/useJobs';
import type { MetadataFilterParams } from '../types/isoDocs';
import type { DocNodeType, DocTreeNode, ReorderItem } from '@/shared/types/doc';

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

function buildSlugMaps(
  nodes: DocTreeNode[],
  slugToId = new Map<string, string>(),
  idToSlug = new Map<string, string>(),
): { slugToId: Map<string, string>; idToSlug: Map<string, string> } {
  for (const node of nodes) {
    slugToId.set(node.slug, node.id);
    idToSlug.set(node.id, node.slug);
    if (node.children.length > 0) {
      buildSlugMaps(node.children, slugToId, idToSlug);
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

function WidgetRenderer({
  widgetKey,
  nodeId,
  isEditor,
}: Readonly<{
  widgetKey: string;
  nodeId: string;
  isEditor: boolean;
}>): JSX.Element {
  const Widget = WIDGET_REGISTRY[widgetKey];
  if (Widget) {
    return <Widget nodeId={nodeId} isEditor={isEditor} />;
  }
  return (
    <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
      Widget not found: <code>{widgetKey}</code>
    </div>
  );
}

const NODE_TYPE_ICON: Record<string, typeof File> = {
  group: Folder,
  registry: Table2,
  widget: Blocks,
};

function GroupChildren({
  nodes,
  onSelect,
}: Readonly<{
  nodes: DocTreeNode[];
  onSelect: (id: string) => void;
}>): JSX.Element {
  return (
    <div className="space-y-1">
      {nodes.map((child) => {
        const Icon = NODE_TYPE_ICON[child.type] ?? File;
        return (
          <button
            key={child.id}
            className="flex items-center gap-2 w-full text-left px-3 py-2 rounded hover:bg-muted text-sm"
            onClick={() => onSelect(child.id)}
          >
            <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span>{child.title}</span>
          </button>
        );
      })}
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
  driveConnected,
  driveExporting,
  driveProgress,
  collapsed,
  onSelect,
  onMove,
  onAdd,
  onToggleFilters,
  onFiltersChange,
  onDriveExport,
  onToggleCollapse,
}: Readonly<{
  tree: DocTreeNode[];
  treeLoading: boolean;
  selectedId: string | null;
  isEditor: boolean;
  collapsed: boolean;
  filtersOpen: boolean;
  filters: MetadataFilterParams;
  driveConnected: boolean;
  driveExporting: boolean;
  driveProgress: number | null;
  onSelect: (id: string) => void;
  onMove: (args: { dragIds: string[]; parentId: string | null; index: number }) => void;
  onAdd: () => void;
  onToggleFilters: () => void;
  onFiltersChange: (filters: MetadataFilterParams) => void;
  onDriveExport: () => void;
  onToggleCollapse: () => void;
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

  const driveExportTitle = driveExporting
    ? (driveProgress ? `Exporting (${driveProgress}%)` : 'Exporting...')
    : 'Export to Google Drive';
  const sidebarVisibility = (() => {
    if (selectedId && !collapsed) return 'hidden md:flex';
    if (collapsed) return 'flex';
    return '';
  })();

  return (
    <div data-iso-tree-sidebar className={`shrink-0 border-r flex flex-col transition-all ${collapsed ? 'w-10' : 'w-full md:w-72'} ${sidebarVisibility}`}>
      {collapsed ? (
        <div className="flex flex-col items-center pt-3 gap-2">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onToggleCollapse} title="Expand sidebar">
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <>
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
              {isEditor && !filtersOpen && driveConnected && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      disabled={driveExporting}
                      title={driveExportTitle}
                    >
                      {driveExporting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Upload className="h-4 w-4" />
                      )}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Export to Google Drive</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will export all documents and registries to Google Drive, replacing any existing versions. Continue?
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={onDriveExport}>Export</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
              {isEditor && !filtersOpen && (
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onAdd}>
                  <Plus className="h-4 w-4" />
                </Button>
              )}
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onToggleCollapse} title="Collapse sidebar">
                <PanelLeftClose className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex-1 min-h-0 p-2">{renderSidebarContent()}</div>
        </>
      )}
    </div>
  );
}

export default function IsoDocs(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
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
  const [driveJobId, setDriveJobId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const canEditIsoDocs = usePermission(Action.ISO_DOCS_EDIT);
  const isAdmin = bypassAuth || canAdmin;
  const isEditor = canEditIsoDocs || isAdmin;

  const { data: tree = [], isLoading: treeLoading } = useIsoDocTree();

  const flat = useMemo(() => flattenTree(tree), [tree]);
  const { slugToId, idToSlug } = useMemo(() => buildSlugMaps(tree), [tree]);

  const pagePath = searchParams.get('page');
  const permalinkId = searchParams.get('id');

  useEffect(() => {
    if (permalinkId && idToSlug.has(permalinkId)) {
      setSearchParams({ page: idToSlug.get(permalinkId)! }, { replace: true });
    }
  }, [permalinkId, idToSlug, setSearchParams]);

  const selectedId = pagePath ? (slugToId.get(pagePath) ?? null) : (permalinkId ?? null);

  const selectedNode = useMemo(
    () => flat.find((n) => n.id === selectedId),
    [flat, selectedId],
  );
  const { data: page } = useIsoDocPage(selectedId, selectedNode?.type === 'page');
  const { data: metadata } = useIsoDocMetadata(selectedId);
  const createNode = useCreateIsoDocNode();
  const updateNode = useUpdateIsoDocNode();
  const deleteNode = useDeleteIsoDocNode();
  const reorder = useReorderIsoDocNodes();
  const savePage = useSaveIsoDocPage(selectedId ?? '');
  const updateMetadata = useUpdateIsoDocMetadata(selectedId ?? '');
  const { data: driveStatus } = useDriveExportStatus();
  const triggerDriveExport = useTriggerDriveExport();
  const { data: driveJob } = useJobStatus(driveJobId);
  const driveExporting = driveJob?.status === 'pending' || driveJob?.status === 'running';

  useEffect(() => {
    if (driveJob?.status === 'completed' || driveJob?.status === 'failed') {
      setDriveJobId(null);
    }
  }, [driveJob?.status]);

  const handleDriveExport = useCallback(() => {
    triggerDriveExport.mutate(undefined, {
      onSuccess: (data) => setDriveJobId(data.job_id),
    });
  }, [triggerDriveExport]);
  const isPage = selectedNode?.type === 'page';
  const isRegistry = selectedNode?.type === 'registry';
  const isWidget = selectedNode?.type === 'widget';
  const nodeTypeLabel = selectedNode?.type ?? 'group';

  const { data: versions } = useIsoDocVersions(historyOpen ? selectedId : null);
  const { data: versionDetail } = useIsoDocVersion(
    selectedVersion === null ? null : selectedId,
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
      const url = new URL(href, globalThis.location.origin);
      const pageSlug = url.searchParams.get('page');
      const nodeId = url.searchParams.get('id');
      if (pageSlug) {
        setSearchParams({ page: pageSlug }, { replace: true });
        setEditing(false);
      } else if (nodeId) {
        const slug = idToSlug.get(nodeId);
        if (slug) {
          setSearchParams({ page: slug }, { replace: true });
          setEditing(false);
        }
      }
    },
    [setSearchParams, idToSlug],
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
    (title: string, type: DocNodeType, registryTypeId?: string, widgetKey?: string) => {
      createNode.mutate(
        {
          title,
          type,
          parent_id: selectedNode?.type === 'group' ? selectedId : null,
          registry_type_id: registryTypeId ?? null,
          widget_key: widgetKey ?? null,
        },
        {
          onSuccess: (node) => {
            setFormOpen(false);
            if (node.type === 'page' || node.type === 'registry' || node.type === 'widget') {
              setSearchParams({ page: node.slug }, { replace: true });
            }
          },
        },
      );
    },
    [createNode, selectedId, selectedNode, setSearchParams],
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
    const hasRegistry = !!contentEl.querySelector('[data-registry-view]');

    const printStyle = document.createElement('style');
    printStyle.id = 'iso-print-style';
    printStyle.textContent = `
      @media print {
        /* Reset all ancestors to flow naturally */
        html, body, #root, #root > *, #root > * > *,
        [data-iso-root], [data-iso-content] {
          display: block !important; position: static !important;
          overflow: visible !important; height: auto !important;
          max-height: none !important; min-height: 0 !important;
          width: 100% !important; flex: none !important;
        }
        [data-iso-content] { padding: 0.5cm !important; }
        /* Hide sidebar, toolbar, actions */
        [data-iso-root] > *:not([data-iso-content]) { display: none !important; }
        [data-registry-toolbar], [data-iso-actions], [data-print-hide] { display: none !important; }
        nav, aside { display: none !important; }
        /* Unclip table content */
        .truncate { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
        .max-w-xs { max-width: none !important; }
        .overflow-x-auto, .overflow-auto { overflow: visible !important; }
        [style*="min-width"] { min-width: 0 !important; }
        /* Table styling */
        table { width: 100% !important; border-collapse: collapse !important; font-size: 9px !important; }
        th, td { border: 1px solid #ccc !important; padding: 3px 5px !important; word-wrap: break-word !important; }
        th { background: #f5f5f5 !important; font-weight: 600 !important; }
        tr { page-break-inside: avoid; }
        a { color: inherit !important; text-decoration: none !important; }
        @page { margin: 1cm; ${hasRegistry ? 'size: landscape;' : ''} }
      }
    `;
    document.head.appendChild(printStyle);
    globalThis.print();
    printStyle.remove();
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
        driveConnected={!!driveStatus?.connected}
        driveExporting={driveExporting}
        driveProgress={driveJob?.progress ?? null}
        collapsed={sidebarCollapsed}
        onSelect={handleSelect}
        onMove={handleMove}
        onAdd={() => setFormOpen(true)}
        onToggleFilters={() => setFiltersOpen((v) => !v)}
        onFiltersChange={setMetadataFilters}
        onDriveExport={handleDriveExport}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
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
        renderRegistryPicker={(value, onChange) => (
          <RegistryTypePicker value={value} onChange={onChange} />
        )}
        showWidgetOption
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
          uploadImage={isoDocsApi.uploadImage}
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
                  </>
                )}
                {(isPage || isRegistry || isWidget) && (
                  <>
                    {!isPage && isEditor && <DropdownMenuSeparator />}
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
                      Delete {nodeTypeLabel}
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
        {isRegistry && selectedNode?.registry_type_id && (
          <div className="space-y-6">
            {metadata && (
              <MetadataPanel
                metadata={metadata}
                onEdit={isEditor ? () => setMetadataEditOpen(true) : undefined}
              />
            )}
            <RegistryView
              nodeId={selectedNode.id}
              registryTypeId={selectedNode.registry_type_id}
              isEditor={isEditor}
            />
          </div>
        )}
        {isWidget && selectedNode?.widget_key && (
          <div className="space-y-6">
            {metadata && (
              <MetadataPanel
                metadata={metadata}
                onEdit={isEditor ? () => setMetadataEditOpen(true) : undefined}
              />
            )}
            <WidgetRenderer widgetKey={selectedNode.widget_key} nodeId={selectedNode.id} isEditor={isEditor} />
          </div>
        )}
        {!isPage && !isRegistry && !isWidget && selectedNode && (
          <GroupChildren nodes={selectedNode.children} onSelect={handleSelect} />
        )}
      </div>
    );
  }
}
