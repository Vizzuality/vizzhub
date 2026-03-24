import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, BookOpen } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { PlaybookTree } from '../components/PlaybookTree';
import { PageViewer } from '../components/PageViewer';
import { PageEditor } from '../components/PageEditor';
import { NodeForm } from '../components/NodeForm';
import {
  usePlaybookTree,
  useCreateNode,
  useReorderNodes,
} from '../hooks/usePlaybookTree';
import { usePlaybookPage, useSavePage } from '../hooks/usePlaybookPage';
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

  const { data: tree = [], isLoading: treeLoading } = usePlaybookTree();
  const { data: page } = usePlaybookPage(selectedId);
  const createNode = useCreateNode();
  const reorder = useReorderNodes();
  const savePage = useSavePage(selectedId ?? '');

  const flat = flattenTree(tree);
  const selectedNode = flat.find((n) => n.id === selectedId);
  const isPage = selectedNode?.type === 'page';

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
        ) : !isPage ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Groups have no content. Select a page.
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
                <Button size="sm" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                {page?.is_public && (
                  <span className="text-xs px-2 py-0.5 rounded bg-green-500/10 text-green-600">
                    Public
                  </span>
                )}
              </div>
            </div>
            <PageViewer content={page?.content ?? ''} />
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
    </div>
  );
}
