import { Tree, NodeRendererProps } from 'react-arborist';
import { ChevronRight, ChevronDown, File, Folder, Globe } from 'lucide-react';
import type { TreeNode } from '../types/playbook';

interface PlaybookTreeProps {
  data: TreeNode[];
  selectedId: string | null;
  onSelect: (id: string, type: 'page' | 'group') => void;
  onMove: (args: {
    dragIds: string[];
    parentId: string | null;
    index: number;
  }) => void;
}

function Node({
  node,
  style,
  dragHandle,
}: NodeRendererProps<TreeNode>): JSX.Element {
  const isGroup = node.data.type === 'group';
  const isPublic = node.data.is_public;

  return (
    <div
      ref={dragHandle}
      style={style}
      className={`flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer text-sm ${
        node.isSelected
          ? 'bg-accent text-accent-foreground'
          : 'hover:bg-muted'
      }`}
      onClick={() => node.toggle()}
    >
      {isGroup ? (
        node.isOpen ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )
      ) : (
        <span className="w-3.5 shrink-0" />
      )}
      {isGroup ? (
        <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
      ) : (
        <File className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      <span className="truncate">{node.data.title}</span>
      {isPublic && (
        <Globe className="h-3 w-3 shrink-0 text-green-500 ml-auto" />
      )}
    </div>
  );
}

export function PlaybookTree({
  data,
  selectedId,
  onSelect,
  onMove,
}: PlaybookTreeProps): JSX.Element {
  return (
    <Tree<TreeNode>
      data={data}
      idAccessor="id"
      childrenAccessor="children"
      selection={selectedId ?? undefined}
      onSelect={(nodes) => {
        const first = nodes[0];
        if (first) {
          onSelect(first.id, first.data.type);
        }
      }}
      onMove={({ dragIds, parentId, index }) => {
        onMove({ dragIds, parentId, index });
      }}
      openByDefault={false}
      width="100%"
      rowHeight={32}
      indent={20}
    >
      {Node}
    </Tree>
  );
}
