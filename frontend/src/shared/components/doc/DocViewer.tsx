import { useEffect, useRef } from 'react';
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
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!onInternalLink || !containerRef.current) return;

    const handler = (e: MouseEvent): void => {
      const target = (e.target as HTMLElement).closest('a');
      if (!target) return;
      const href = target.getAttribute('href');
      if (href?.startsWith('/iso/docs')) {
        e.preventDefault();
        onInternalLink(href);
      }
    };

    const el = containerRef.current;
    el.addEventListener('click', handler);
    return () => el.removeEventListener('click', handler);
  }, [onInternalLink]);

  if (!content) {
    return (
      <p className="text-muted-foreground italic">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div
      ref={containerRef}
      data-color-mode={resolvedTheme === 'dark' ? 'dark' : 'light'}
      className="overflow-hidden [&_table]:block [&_table]:overflow-x-auto [&_table]:max-w-full"
      style={{ overflowWrap: 'anywhere' }}
    >
      <MDEditor.Markdown source={content} remarkPlugins={remarkPlugins} />
    </div>
  );
}
