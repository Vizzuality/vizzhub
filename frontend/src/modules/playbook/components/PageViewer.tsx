import MDEditor from '@uiw/react-md-editor';

interface PageViewerProps {
  content: string;
}

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
      <MDEditor.Markdown source={content} />
    </div>
  );
}
