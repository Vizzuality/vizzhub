import { useCallback } from 'react';
import { NodeForm as SharedNodeForm } from '@/shared/components/doc/NodeForm';
import type { DocNodeType } from '@/shared/types/doc';

interface PlaybookNodeFormProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (title: string, type: 'page' | 'group') => void;
  readonly isLoading: boolean;
  readonly parentId: string | null;
}

export function NodeForm({
  open,
  onClose,
  onSubmit,
  isLoading,
  parentId,
}: PlaybookNodeFormProps): JSX.Element {
  const handleSubmit = useCallback(
    (title: string, type: DocNodeType) => {
      onSubmit(title, type as 'page' | 'group');
    },
    [onSubmit],
  );

  return (
    <SharedNodeForm
      open={open}
      onClose={onClose}
      onSubmit={handleSubmit}
      isLoading={isLoading}
      parentId={parentId}
      rootLabel="Add to playbook"
    />
  );
}
