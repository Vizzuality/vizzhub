import { useState, useCallback, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, BookOpen, MoreHorizontal, Trash2, Globe, Lock, History, File, Folder, ArrowLeft, Pencil } from 'lucide-react';
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
} from '@/shared/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { PlaybookTree } from '../components/PlaybookTree';
import { PageViewer } from '../components/PageViewer';
import { PageEditor } from '../components/PageEditor';
import { NodeForm } from '../components/NodeForm';
import { VersionHistoryDialog } from '../components/VersionHistoryDialog';
import { PublishButton } from '../components/PublishButton';
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

function buildSlugMaps(
  nodes: TreeNode[],
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

const MAX_TREE_DEPTH = 10;

function getNodeDepth(tree: TreeNode[], nodeId: string, depth = 1): number | null {
  for (const node of tree) {
    if (node.id === nodeId) return depth;
    if (node.children.length > 0) {
      const found = getNodeDepth(node.children, nodeId, depth + 1);
      if (found !== null) return found;
    }
  }
  return null;
}

function getSubtreeDepth(node: TreeNode): number {
  if (node.children.length === 0) return 1;
  return 1 + Math.max(...node.children.map(getSubtreeDepth));
}

function findNodeById(tree: TreeNode[], id: string): TreeNode | null {
  for (const node of tree) {
    if (node.id === id) return node;
    const found = findNodeById(node.children, id);
    if (found) return found;
  }
  return null;
}

function collectDescendantIds(node: TreeNode, out: Set<string>): void {
  for (const child of node.children) {
    out.add(child.id);
    collectDescendantIds(child, out);
  }
}

function validateReorder(
  tree: TreeNode[],
  dragIds: string[],
  parentId: string | null,
): { ok: true } | { ok: false; reason: string } {
  if (parentId !== null && dragIds.includes(parentId)) {
    return { ok: false, reason: 'Cannot move a node into itself.' };
  }

  for (const dragId of dragIds) {
    const dragNode = findNodeById(tree, dragId);
    if (!dragNode) continue;

    if (parentId !== null) {
      const descendants = new Set<string>();
      collectDescendantIds(dragNode, descendants);
      if (descendants.has(parentId)) {
        return { ok: false, reason: 'Cannot move a node into one of its descendants.' };
      }
    }

    const parentDepth = parentId === null ? 0 : (getNodeDepth(tree, parentId) ?? 0);
    const subtreeDepth = getSubtreeDepth(dragNode);
    if (parentDepth + subtreeDepth > MAX_TREE_DEPTH) {
      return {
        ok: false,
        reason: `Move would exceed the maximum tree depth of ${MAX_TREE_DEPTH}.`,
      };
    }
  }

  return { ok: true };
}

function GroupChildren({
  nodes,
  onSelect,
}: Readonly<{
  nodes: TreeNode[];
  onSelect: (id: string) => void;
}>): JSX.Element {
  return (
    <div className="space-y-1">
      {nodes.map((child) => (
        <button
          key={child.id}
          type="button"
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
  isEditor,
  onSelect,
  onMove,
  onAdd,
}: Readonly<{
  tree: TreeNode[];
  treeLoading: boolean;
  selectedId: string | null;
  isEditor: boolean;
  onSelect: (id: string) => void;
  onMove: (args: { dragIds: string[]; parentId: string | null; index: number }) => void;
  onAdd: () => void;
}>): JSX.Element {
  const getSidebarContent = (): JSX.Element => {
    if (treeLoading) {
      return <p className="text-sm text-muted-foreground p-2">Loading...</p>;
    }
    if (tree.length > 0) {
      return (
        <PlaybookTree
          data={tree}
          selectedId={selectedId}
          onSelect={onSelect}
          onMove={isEditor ? onMove : undefined}
        />
      );
    }
    return (
      <div className="text-center py-8 px-4">
        <p className="text-sm text-muted-foreground mb-3">No pages yet</p>
        {isEditor && <Button size="sm" onClick={onAdd}>Create your first page</Button>}
      </div>
    );
  };
  const sidebarContent = getSidebarContent();

  return (
    <div className={`w-full md:w-72 shrink-0 border-r flex flex-col ${selectedId ? 'hidden md:flex' : ''}`}>
      <div className="flex items-center justify-between p-3 border-b">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <BookOpen className="h-4 w-4" />
          Playbook
        </div>
        {isEditor && (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onAdd}>
            <Plus className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-2">{sidebarContent}</div>
    </div>
  );
}

export default function Playbook(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const [editing, setEditing] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const canEditPlaybook = usePermission(Action.PLAYBOOK_EDIT);
  const isAdmin = bypassAuth || canAdmin;
  const isEditor = canEditPlaybook || isAdmin;

  const { data: tree = [], isLoading: treeLoading } = usePlaybookTree();

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
      const check = validateReorder(tree, dragIds, parentId);
      if (!check.ok) {
        alert(check.reason);
        return;
      }
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

  const handleTogglePublic = useCallback(() => {
    if (!selectedId || !page) return;
    updateNode.mutate({
      id: selectedId,
      data: { is_public: !page.is_public },
    });
  }, [selectedId, page, updateNode]);

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

  const descendantCount = useMemo(() => {
    if (!selectedNode) return 0;
    const countChildren = (node: TreeNode): number =>
      node.children.reduce((sum, c) => sum + 1 + countChildren(c), 0);
    return countChildren(selectedNode);
  }, [selectedNode]);

  const itemWord = descendantCount === 1 ? 'item' : 'items';
  const deleteDescription = selectedNode?.type === 'group' && descendantCount > 0
    ? `This will also delete ${descendantCount} ${itemWord} inside this group. This action cannot be undone.`
    : 'This action cannot be undone.';

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      <TreeSidebar
        tree={tree}
        treeLoading={treeLoading}
        selectedId={selectedId}
        isEditor={isEditor}
        onSelect={handleSelect}
        onMove={handleMove}
        onAdd={() => setFormOpen(true)}
      />

      <div className={`flex-1 overflow-auto p-6 bg-card ${selectedId ? '' : 'hidden md:block'}`}>
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
          <h1 className="text-2xl font-semibold">Vizzuality Playbook</h1>
          <p className="text-muted-foreground">Select a page from the tree to start</p>
        </div>
      );
    }

    if (editing) {
      return (
        <PageEditor
          key={selectedId ?? 'none'}
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
            {isEditor && <PublishButton />}
            {isPage && page?.is_public && (
              <span className="flex items-center gap-1.5 text-xs">
                <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                <span>Public</span>
              </span>
            )}
            {isPage && isEditor && (
              <Button size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {isEditor && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={handleRenameOpen}>
                    <Pencil className="h-4 w-4 mr-2" />
                    Rename
                  </DropdownMenuItem>
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
            )}
          </div>
        </div>
        {isPage && <PageViewer content={page?.content ?? ''} />}
        {!isPage && selectedNode && (
          <GroupChildren nodes={selectedNode.children} onSelect={handleSelect} />
        )}
      </div>
    );
  }
}
