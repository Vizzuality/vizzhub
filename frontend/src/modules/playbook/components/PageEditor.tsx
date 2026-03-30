import { DocEditor } from '@/shared/components/doc/DocEditor';
import { playbookApi } from '../services/playbook';

interface PageEditorProps {
  readonly initialContent: string;
  readonly onSave: (content: string) => void;
  readonly onCancel: () => void;
  readonly isSaving: boolean;
}

export function PageEditor({
  initialContent,
  onSave,
  onCancel,
  isSaving,
}: PageEditorProps): JSX.Element {
  return (
    <DocEditor
      initialContent={initialContent}
      onSave={onSave}
      onCancel={onCancel}
      isSaving={isSaving}
      uploadImage={playbookApi.uploadImage}
    />
  );
}
