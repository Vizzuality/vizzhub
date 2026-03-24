import MDEditor from '@uiw/react-md-editor';
import remarkBreaks from 'remark-breaks';

interface PageViewerProps {
  content: string;
}

const remarkPlugins = [remarkBreaks];

export function PageViewer({ content }: PageViewerProps): JSX.Element {
  if (!content) {
    return (
      <p className="text-muted-foreground italic">
        This page has no content yet. Click Edit to start writing.
      </p>
    );
  }

  return (
    <div data-color-mode="auto">
      <MDEditor.Markdown source={content} remarkPlugins={remarkPlugins} />
    </div>
  );
}
