import { useState, useCallback, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, BookOpen, MoreHorizontal, Trash2, Globe, Lock, History, File, Folder, ArrowLeft } from 'lucide-react';
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
import { PlaybookTree } from '../components/PlaybookTree';
import { PageViewer } from '../components/PageViewer';
import { PageEditor } from '../components/PageEditor';
import { NodeForm } from '../components/NodeForm';
import { VersionHistoryDialog } from '../components/VersionHistoryDialog';
import {
  usePlaybookTree,
  useCreateNode,
  useUpdateNode,
  useDeleteNode,
  useReorderNodes,
} from '../hooks/usePlaybookTree';
import { usePlaybookPage, useSavePage } from '../hooks/usePlaybookPage';
import { usePermission, Action } from '@/core/permissions';
import type { TreeNode, ReorderItem } from '../types/playbook';

function flattenTree(nodes: TreeNode[]): TreeNode[] {
  const result: TreeNode[] = [];
  for (const node of nodes) {
    result.push(node);
    if (node.children.length > 0) {
      result.push(...flattenTree(node.children));
    }
  }
  return result;
}

function buildSlugPaths(
  nodes: TreeNode[],
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
  tree: TreeNode[],
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
  children,
  onSelect,
}: Readonly<{
  children: TreeNode[];
  onSelect: (id: string) => void;
}>): JSX.Element {
  return (
    <div className="space-y-1">
      {children.map((child) => (
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
          {child.is_public && (
            <Globe className="h-3 w-3 shrink-0 text-green-500 ml-auto" />
          )}
        </button>
      ))}
    </div>
  );
}

function TreeSidebar({
  tree,
  treeLoading,
  selectedId,
  onSelect,
  onMove,
  onAdd,
}: Readonly<{
  tree: TreeNode[];
  treeLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onMove: (args: { dragIds: string[]; parentId: string | null; index: number }) => void;
  onAdd: () => void;
}>): JSX.Element {
  const sidebarContent = treeLoading ? (
    <p className="text-sm text-muted-foreground p-2">Loading...</p>
  ) : tree.length > 0 ? (
    <PlaybookTree
      data={tree}
      selectedId={selectedId}
      onSelect={onSelect}
      onMove={onMove}
    />
  ) : (
    <div className="text-center py-8 px-4">
      <p className="text-sm text-muted-foreground mb-3">No pages yet</p>
      <Button size="sm" onClick={onAdd}>Create your first page</Button>
    </div>
  );

  return (
    <div className={`w-full md:w-72 shrink-0 border-r flex flex-col ${selectedId ? 'hidden md:flex' : ''}`}>
      <div className="flex items-center justify-between p-3 border-b">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <BookOpen className="h-4 w-4" />
          Playbook
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onAdd}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-2">{sidebarContent}</div>
    </div>
  );
}

export default function Playbook(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const { setOpen } = useSidebar();
  useEffect(() => { setOpen(false); }, [setOpen]);
  const [editing, setEditing] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const isAdmin = bypassAuth || canAdmin;

  const { data: tree = [], isLoading: treeLoading } = usePlaybookTree();

  const flat = useMemo(() => flattenTree(tree), [tree]);
  const { slugToId, idToSlug } = useMemo(() => buildSlugPaths(tree), [tree]);

  const pagePath = searchParams.get('page');
  const selectedId = pagePath ? (slugToId.get(pagePath) ?? null) : null;

  const { data: page } = usePlaybookPage(selectedId);
  const createNode = useCreateNode();
  const updateNode = useUpdateNode();
  const deleteNode = useDeleteNode();
  const reorder = useReorderNodes();
  const savePage = useSavePage(selectedId ?? '');
  const selectedNode = useMemo(
    () => flat.find((n) => n.id === selectedId),
    [flat, selectedId],
  );
  const isPage = selectedNode?.type === 'page';

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

  const handleTogglePublic = useCallback(() => {
    if (!selectedId || !page) return;
    updateNode.mutate({
      id: selectedId,
      data: { is_public: !page.is_public },
    });
  }, [selectedId, page, updateNode]);

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

  const descendantCount = useMemo(() => {
    if (!selectedNode) return 0;
    const countChildren = (node: TreeNode): number =>
      node.children.reduce((sum, c) => sum + 1 + countChildren(c), 0);
    return countChildren(selectedNode);
  }, [selectedNode]);

  const deleteDescription = selectedNode?.type === 'group' && descendantCount > 0
    ? `This will also delete ${descendantCount} ${descendantCount === 1 ? 'item' : 'items'} inside this group. This action cannot be undone.`
    : 'This action cannot be undone.';

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      <TreeSidebar
        tree={tree}
        treeLoading={treeLoading}
        selectedId={selectedId}
        onSelect={handleSelect}
        onMove={handleMove}
        onAdd={() => setFormOpen(true)}
      />

      <div className={`flex-1 overflow-auto p-6 ${selectedId ? '' : 'hidden md:block'}`}>
        {renderContent()}
      </div>

      <NodeForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={handleCreateNode}
        isLoading={createNode.isPending}
        parentId={selectedNode?.type === 'group' ? selectedId : null}
      />

      <VersionHistoryDialog
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        nodeId={selectedId}
        currentVersion={page?.version ?? 0}
        onRestore={handleRestore}
        isRestoring={savePage.isPending}
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
    </div>
  );

  function renderContent(): JSX.Element {
    if (!selectedId) {
      return (
        <div className="flex flex-col items-center pt-[20vh] gap-2">
          <h1 className="text-2xl font-semibold">Vizzuality Playbook</h1>
          <p className="text-muted-foreground">Select a page from the tree to start</p>
        </div>
      );
    }

    if (editing) {
      return (
        <PageEditor
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
          <div className="flex items-center gap-2">
            {isPage && (
              <>
                <Button size="sm" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                {page?.is_public && (
                  <span className="flex items-center gap-1.5 text-xs">
                    <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                    Public
                  </span>
                )}
              </>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {isPage && (
                  <DropdownMenuItem onClick={handleTogglePublic}>
                    {page?.is_public ? (
                      <><Lock className="h-4 w-4 mr-2" /> Make private</>
                    ) : (
                      <><Globe className="h-4 w-4 mr-2" /> Make public</>
                    )}
                  </DropdownMenuItem>
                )}
                {isPage && isAdmin && (
                  <DropdownMenuItem onClick={() => setHistoryOpen(true)}>
                    <History className="h-4 w-4 mr-2" />
                    Version history
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => setDeleteConfirmOpen(true)}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete {selectedNode?.type === 'group' ? 'group' : 'page'}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        {isPage ? (
          <PageViewer content={page?.content ?? ''} />
        ) : selectedNode ? (
          <GroupChildren children={selectedNode.children} onSelect={handleSelect} />
        ) : null}
      </div>
    );
  }
}
