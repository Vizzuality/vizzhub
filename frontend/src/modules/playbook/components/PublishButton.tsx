import { useState, useRef, useEffect } from 'react';
import { Globe, Loader2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';
import { usePublishPlaybook, usePublishStatus } from '../hooks/usePublishPlaybook';
import { formatRelativeTime } from '@/utils/dateUtils';

export function PublishButton() {
  const publish = usePublishPlaybook();
  const { data: status } = usePublishStatus();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const prevStatusRef = useRef(status?.status);

  const isPublishing = status?.status === 'running' || publish.isPending;

  useEffect(() => {
    if (prevStatusRef.current === 'running' && status?.status === 'completed') {
      setMessage({ text: `${status.page_count} pages published`, type: 'success' });
      setTimeout(() => setMessage(null), 5000);
    }
    if (prevStatusRef.current === 'running' && status?.status === 'failed') {
      setMessage({ text: status.error_message || 'Publish failed', type: 'error' });
      setTimeout(() => setMessage(null), 8000);
    }
    prevStatusRef.current = status?.status;
  }, [status?.status, status?.page_count, status?.error_message]);

  const handlePublish = (e: React.MouseEvent): void => {
    e.preventDefault();
    setOpen(false);
    setMessage(null);
    publish.mutate(undefined, {
      onError: () => {
        setMessage({ text: 'Failed to start publish', type: 'error' });
        setTimeout(() => setMessage(null), 5000);
      },
    });
  };

  const statusText = status?.status === 'completed' && status.completed_at
    ? `Published ${formatRelativeTime(status.completed_at)} (${status.page_count} pages)`
    : status?.status === 'failed'
      ? 'Last publish failed'
      : null;

  return (
    <div className="flex items-center gap-2">
      {message && (
        <span className={`text-xs ${message.type === 'success' ? 'text-green-600' : 'text-destructive'}`}>
          {message.text}
        </span>
      )}
      {!message && statusText && (
        <span className="text-xs text-muted-foreground hidden sm:inline">{statusText}</span>
      )}
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger asChild>
          <Button size="sm" variant="outline" disabled={isPublishing}>
            {isPublishing ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Globe className="h-4 w-4 mr-1.5" />
            )}
            {isPublishing ? 'Publishing...' : 'Publish'}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Publish Playbook</AlertDialogTitle>
            <AlertDialogDescription>
              This will publish all public pages to the external playbook site. Continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePublish}>Publish</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
