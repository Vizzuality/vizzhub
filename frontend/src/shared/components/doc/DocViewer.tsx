import { useCallback } from 'react';
import MDEditor from '@uiw/react-md-editor';
import remarkBreaks from 'remark-breaks';
import { useTheme } from 'next-themes';

interface DocViewerProps {
  readonly content: string;
  readonly emptyMessage?: string;
  readonly onInternalLink?: (path: string) => void;
}

const remarkPlugins = [remarkBreaks];

export function DocViewer({
  content,
  emptyMessage = 'This page has no content yet. Click Edit to start writing.',
  onInternalLink,
}: DocViewerProps): JSX.Element {
  const { resolvedTheme } = useTheme();

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!onInternalLink) return;
      const target = (e.target as HTMLElement).closest('a');
      if (!target) return;
      const href = target.getAttribute('href');
      if (href?.startsWith('/iso/docs')) {
        e.preventDefault();
        onInternalLink(href);
      }
    },
    [onInternalLink],
  );

  if (!content) {
    return (
      <p className="text-muted-foreground italic">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div
      data-color-mode={resolvedTheme === 'dark' ? 'dark' : 'light'}
      onClick={handleClick}
    >
      <MDEditor.Markdown source={content} remarkPlugins={remarkPlugins} />
    </div>
  );
}
