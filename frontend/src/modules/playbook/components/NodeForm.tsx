import { NodeForm as SharedNodeForm } from '@/shared/components/doc/NodeForm';

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
  return (
    <SharedNodeForm
      open={open}
      onClose={onClose}
      onSubmit={onSubmit}
      isLoading={isLoading}
      parentId={parentId}
      rootLabel="Add to playbook"
    />
  );
}
