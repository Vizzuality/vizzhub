import { useState } from 'react';
import MDEditor from '@uiw/react-md-editor';
import remarkBreaks from 'remark-breaks';
import { Button } from '@/shared/components/ui/button';

interface PageEditorProps {
  initialContent: string;
  onSave: (content: string) => void;
  onCancel: () => void;
  isSaving: boolean;
}

export function PageEditor({
  initialContent,
  onSave,
  onCancel,
  isSaving,
}: PageEditorProps): JSX.Element {
  const [content, setContent] = useState(initialContent);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button size="sm" onClick={() => onSave(content)} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
      </div>
      <div data-color-mode="auto">
        <MDEditor
          value={content}
          onChange={(val) => setContent(val ?? '')}
          height={500}
          preview="edit"
          previewOptions={{ remarkPlugins: [remarkBreaks] }}
        />
      </div>
    </div>
  );
}
