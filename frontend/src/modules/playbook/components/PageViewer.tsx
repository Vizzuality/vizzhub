import MDEditor from '@uiw/react-md-editor';
import remarkBreaks from 'remark-breaks';
import { useTheme } from 'next-themes';

interface PageViewerProps {
  readonly content: string;
}

const remarkPlugins = [remarkBreaks];

export function PageViewer({ content }: PageViewerProps): JSX.Element {
  const { resolvedTheme } = useTheme();

  if (!content) {
    return (
      <p className="text-muted-foreground italic">
        This page has no content yet. Click Edit to start writing.
      </p>
    );
  }

  return (
    <div data-color-mode={resolvedTheme === 'dark' ? 'dark' : 'light'}>
      <MDEditor.Markdown source={content} remarkPlugins={remarkPlugins} />
    </div>
  );
}
