import { Globe } from 'lucide-react';
import { DocTree } from '@/shared/components/doc/DocTree';
import type { TreeNode } from '../types/playbook';
import type { DocTreeNode } from '@/shared/types/doc';

interface PlaybookTreeProps {
  readonly data: TreeNode[];
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
  readonly onMove?: (args: {
    dragIds: string[];
    parentId: string | null;
    index: number;
  }) => void;
}

function renderPublicIndicator(node: DocTreeNode): React.ReactNode {
  const playbookNode = node as TreeNode;
  if (!playbookNode.is_public) return null;
  return <Globe className="h-3 w-3 shrink-0 text-green-500 ml-auto" />;
}

export function PlaybookTree({
  data,
  selectedId,
  onSelect,
  onMove,
}: PlaybookTreeProps): JSX.Element {
  return (
    <DocTree
      data={data as DocTreeNode[]}
      selectedId={selectedId}
      onSelect={onSelect}
      onMove={onMove}
      renderNodeExtra={renderPublicIndicator}
    />
  );
}
