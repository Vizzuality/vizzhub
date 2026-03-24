import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, BookOpen, MoreHorizontal, Trash2, Globe, Lock, History } from 'lucide-react';
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
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { PlaybookTree } from '../components/PlaybookTree';
import { PageViewer } from '../components/PageViewer';
import { PageEditor } from '../components/PageEditor';
import { NodeForm } from '../components/NodeForm';
import {
  usePlaybookTree,
  useCreateNode,
  useUpdateNode,
  useDeleteNode,
  useReorderNodes,
} from '../hooks/usePlaybookTree';
import { usePlaybookPage, useSavePage } from '../hooks/usePlaybookPage';
import { usePlaybookVersions } from '../hooks/usePlaybookVersions';
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

export default function Playbook(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get('node');
  const [editing, setEditing] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const isAdmin = bypassAuth || canAdmin;

  const { data: tree = [], isLoading: treeLoading } = usePlaybookTree();
  const { data: page } = usePlaybookPage(selectedId);
  const createNode = useCreateNode();
  const updateNode = useUpdateNode();
  const deleteNode = useDeleteNode();
  const reorder = useReorderNodes();
  const savePage = useSavePage(selectedId ?? '');

  const flat = useMemo(() => flattenTree(tree), [tree]);
  const selectedNode = useMemo(
    () => flat.find((n) => n.id === selectedId),
    [flat, selectedId],
  );
  const isPage = selectedNode?.type === 'page';

  const { data: versions } = usePlaybookVersions(
    historyOpen && isPage ? selectedId : null,
  );

  const handleSelect = useCallback(
    (id: string) => {
      setSearchParams({ node: id }, { replace: true });
      setEditing(false);
    },
    [setSearchParams],
  );

  const handleMove = useCallback(
    ({
      dragIds,
      parentId,
      index,
    }: {
      dragIds: string[];
      parentId: string | null;
      index: number;
    }) => {
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
              alert(
                'This page was edited by someone else. Your changes have been saved as the latest version.',
              );
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
              setSearchParams({ node: node.id }, { replace: true });
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

  const descendantCount = useMemo(() => {
    if (!selectedNode) return 0;
    const countChildren = (node: TreeNode): number =>
      node.children.reduce((sum, c) => sum + 1 + countChildren(c), 0);
    return countChildren(selectedNode);
  }, [selectedNode]);

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Sidebar Tree */}
      <div className="w-72 shrink-0 border-r flex flex-col">
        <div className="flex items-center justify-between p-3 border-b">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <BookOpen className="h-4 w-4" />
            Playbook
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setFormOpen(true)}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-auto p-2">
          {treeLoading ? (
            <p className="text-sm text-muted-foreground p-2">Loading...</p>
          ) : tree.length === 0 ? (
            <div className="text-center py-8 px-4">
              <p className="text-sm text-muted-foreground mb-3">
                No pages yet
              </p>
              <Button size="sm" onClick={() => setFormOpen(true)}>
                Create your first page
              </Button>
            </div>
          ) : (
            <PlaybookTree
              data={tree}
              selectedId={selectedId}
              onSelect={handleSelect}
              onMove={handleMove}
            />
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto p-6">
        {!selectedId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Select a page from the tree
          </div>
        ) : editing ? (
          <PageEditor
            initialContent={page?.content ?? ''}
            onSave={handleSave}
            onCancel={() => setEditing(false)}
            isSaving={savePage.isPending}
          />
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h1 className="text-2xl font-semibold">{selectedNode?.title}</h1>
              <div className="flex items-center gap-2">
                {isPage && (
                  <>
                    <Button size="sm" onClick={() => setEditing(true)}>
                      Edit
                    </Button>
                    {page?.is_public && (
                      <span className="text-xs px-2 py-0.5 rounded bg-green-500/10 text-green-600">
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
                          <>
                            <Lock className="h-4 w-4 mr-2" />
                            Make private
                          </>
                        ) : (
                          <>
                            <Globe className="h-4 w-4 mr-2" />
                            Make public
                          </>
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
            ) : (
              <p className="text-muted-foreground">
                This group contains {descendantCount} {descendantCount === 1 ? 'item' : 'items'}.
              </p>
            )}
          </div>
        )}
      </div>

      <NodeForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={handleCreateNode}
        isLoading={createNode.isPending}
        parentId={selectedNode?.type === 'group' ? selectedId : null}
      />

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Version history</DialogTitle>
          </DialogHeader>
          <div className="max-h-96 overflow-auto">
            {versions && versions.length > 0 ? (
              <div className="space-y-1">
                {versions.map((v) => (
                  <div
                    key={v.version}
                    className="flex items-center justify-between py-2.5 px-3 rounded hover:bg-muted text-sm"
                  >
                    <div className="flex flex-col gap-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">v{v.version}</span>
                        {v.created_by_name && (
                          <span className="text-muted-foreground">{v.created_by_name}</span>
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(v.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-mono">
                      {v.lines_added > 0 && (
                        <span className="text-green-600">+{v.lines_added}</span>
                      )}
                      {v.lines_removed > 0 && (
                        <span className="text-red-500">-{v.lines_removed}</span>
                      )}
                      {v.lines_added === 0 && v.lines_removed === 0 && v.version > 1 && (
                        <span className="text-muted-foreground">no changes</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No versions yet
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete &ldquo;{selectedNode?.title}&rdquo;?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {selectedNode?.type === 'group' && descendantCount > 0
                ? `This will also delete ${descendantCount} ${descendantCount === 1 ? 'item' : 'items'} inside this group. `
                : ''}
              This action cannot be undone.
            </AlertDialogDescription>
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
}
