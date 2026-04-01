import { useRef, useState, useEffect } from 'react';
import { Tree, NodeRendererProps } from 'react-arborist';
import { ChevronRight, ChevronDown, File, Folder, Table2 } from 'lucide-react';
import type { DocTreeNode } from '@/shared/types/doc';

interface DocTreeProps {
  readonly data: DocTreeNode[];
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
  readonly onMove?: (args: {
    dragIds: string[];
    parentId: string | null;
    index: number;
  }) => void;
  readonly renderNodeExtra?: (node: DocTreeNode) => React.ReactNode;
}

function Node({
  node,
  style,
  dragHandle,
  renderExtra,
}: NodeRendererProps<DocTreeNode> & {
  renderExtra?: (node: DocTreeNode) => React.ReactNode;
}): JSX.Element {
  const isGroup = node.data.type === 'group';
  const isRegistry = node.data.type === 'registry';

  return (
    <div
      ref={dragHandle}
      style={style}
      className={`flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer text-sm ${
        node.isSelected
          ? 'bg-accent text-accent-foreground'
          : 'hover:bg-muted'
      }`}
      role="treeitem"
      aria-selected={node.isSelected}
      tabIndex={0}
      onClick={() => node.toggle()}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') node.toggle(); }}
    >
      {!isGroup && <span className="w-3.5 shrink-0" />}
      {isGroup && node.isOpen && <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
      {isGroup && !node.isOpen && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
      {isGroup && (
        <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      {isRegistry && (
        <Table2 className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      {!isGroup && !isRegistry && (
        <File className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      <span className="truncate">{node.data.title}</span>
      {renderExtra?.(node.data)}
    </div>
  );
}

export function DocTree({
  data,
  selectedId,
  onSelect,
  onMove,
  renderNodeExtra,
}: DocTreeProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(400);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const h = entries[0]?.contentRect.height;
      if (h && h > 0) setHeight(h);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="h-full min-h-0">
      <Tree<DocTreeNode>
        data={data}
        idAccessor="id"
        childrenAccessor="children"
        selection={selectedId ?? undefined}
        onSelect={(nodes) => {
          const first = nodes[0];
          if (first) {
            onSelect(first.id);
          }
        }}
        disableDrag={!onMove}
        disableDrop={!onMove}
        onMove={onMove ? ({ dragIds, parentId, index }) => {
          onMove({ dragIds, parentId, index });
        } : undefined}
        openByDefault={false}
        width="100%"
        height={height}
        rowHeight={32}
        indent={20}
      >
        {(props) => <Node {...props} renderExtra={renderNodeExtra} />}
      </Tree>
    </div>
  );
}
