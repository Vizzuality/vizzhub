import { useState } from 'react';
import MDEditor from '@uiw/react-md-editor';
import remarkBreaks from 'remark-breaks';
import { useTheme } from 'next-themes';
import { Button } from '@/shared/components/ui/button';

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
  const [content, setContent] = useState(initialContent);
  const { resolvedTheme } = useTheme();
  const colorMode = resolvedTheme === 'dark' ? 'dark' : 'light';

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
      <div data-color-mode={colorMode} className="[&_.w-md-editor-toolbar_svg]:!w-4 [&_.w-md-editor-toolbar_svg]:!h-4">
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
