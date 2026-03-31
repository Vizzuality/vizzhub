import { useState, useCallback, useRef } from 'react';
import MDEditor, { commands } from '@uiw/react-md-editor';
import remarkBreaks from 'remark-breaks';
import { useTheme } from 'next-themes';
import { ImagePlus } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';

interface DocEditorProps {
  readonly initialContent: string;
  readonly onSave: (content: string) => void;
  readonly onCancel: () => void;
  readonly isSaving: boolean;
  readonly uploadImage?: (file: File) => Promise<string>;
}

const IMAGE_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp,image/svg+xml';
const IMAGE_TYPES = new Set(IMAGE_ACCEPT.split(','));

function extractImages(dt: DataTransfer): File[] {
  return Array.from(dt.files).filter((f) => IMAGE_TYPES.has(f.type));
}

const filteredCommands = commands.getCommands().filter((cmd) => cmd.name !== 'image');

export function DocEditor({
  initialContent,
  onSave,
  onCancel,
  isSaving,
  uploadImage,
}: DocEditorProps): JSX.Element {
  const [content, setContent] = useState(initialContent);
  const [uploading, setUploading] = useState(false);
  const [editorKey, setEditorKey] = useState(0);
  const { resolvedTheme } = useTheme();
  const colorMode = resolvedTheme === 'dark' ? 'dark' : 'light';
  const wrapperRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cursorPosRef = useRef<number | null>(null);

  const saveCursorPos = useCallback((): void => {
    const ta = wrapperRef.current?.querySelector('textarea');
    cursorPosRef.current = ta?.selectionStart ?? null;
  }, []);

  const insertAtCursor = useCallback((prev: string, markdown: string): string => {
    const pos = cursorPosRef.current;
    if (pos !== null && pos <= prev.length) {
      return prev.slice(0, pos) + markdown + prev.slice(pos);
    }
    return prev + markdown;
  }, []);

  const uploadAndInsert = useCallback(
    async (files: File[]): Promise<void> => {
      if (files.length === 0 || !uploadImage) return;
      setUploading(true);
      try {
        const markdownParts: string[] = [];
        for (const file of files) {
          const url = await uploadImage(file);
          markdownParts.push(`![${file.name}](${url})`);
        }
        const markdown = '\n' + markdownParts.join('\n') + '\n';
        setContent((prev) => insertAtCursor(prev, markdown));
        setEditorKey((k) => k + 1);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        alert(`Image upload failed: ${msg}`);
      } finally {
        setUploading(false);
      }
    },
    [insertAtCursor, uploadImage],
  );

  const onDrop = useCallback(
    (e: React.DragEvent): void => {
      const images = extractImages(e.dataTransfer);
      if (images.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        saveCursorPos();
        uploadAndInsert(images);
      }
    },
    [uploadAndInsert, saveCursorPos],
  );

  const onPaste = useCallback(
    (e: React.ClipboardEvent): void => {
      const images = extractImages(e.clipboardData);
      if (images.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        saveCursorPos();
        uploadAndInsert(images);
      }
    },
    [uploadAndInsert, saveCursorPos],
  );

  const handleImageClick = useCallback((): void => {
    saveCursorPos();
    fileInputRef.current?.click();
  }, [saveCursorPos]);

  const onFileSelected = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const files = Array.from(e.target.files ?? []);
      if (files.length > 0) uploadAndInsert(files);
      e.target.value = '';
    },
    [uploadAndInsert],
  );

  return (
    <div className="flex flex-col h-full">
      {uploadImage && (
        <input
          ref={fileInputRef}
          type="file"
          accept={IMAGE_ACCEPT}
          className="hidden"
          onChange={onFileSelected}
        />
      )}
      <div className="flex items-center justify-end gap-2 shrink-0 pb-2">
        {uploading && <span className="text-sm text-muted-foreground">Uploading image...</span>}
        {uploadImage && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleImageClick}
            disabled={uploading}
          >
            <ImagePlus className="h-4 w-4 mr-1" />
            Image
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onCancel} disabled={isSaving || uploading}>
          Cancel
        </Button>
        <Button size="sm" onClick={() => onSave(content)} disabled={isSaving || uploading}>
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
      </div>
      <div
        ref={wrapperRef}
        data-color-mode={colorMode}
        className="flex-1 min-h-0 [&_.w-md-editor-toolbar_svg]:!w-4 [&_.w-md-editor-toolbar_svg]:!h-4"
        onDropCapture={uploadImage ? onDrop : undefined}
        onPasteCapture={uploadImage ? onPaste : undefined}
      >
        <MDEditor
          key={editorKey}
          value={content}
          onChange={(val) => setContent(val ?? '')}
          height="100%"
          preview="edit"
          commands={filteredCommands}
          previewOptions={{ remarkPlugins: [remarkBreaks] }}
        />
      </div>
    </div>
  );
}
