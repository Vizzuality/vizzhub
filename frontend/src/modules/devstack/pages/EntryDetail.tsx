import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Pencil, Star, Trash2 } from 'lucide-react';
import MDEditor from '@uiw/react-md-editor';
import { usePermission, Action } from '@/core/permissions';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent } from '@/shared/components/ui/card';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { useDevstackEntry, useDeleteDevstackEntry } from '../hooks/useDevstack';
import { EntryForm } from '../components/EntryForm';
import { InstallMethodBadge } from '../components/EntryBadges';
import { toRawGithubUrl } from '../utils/github';

export default function EntryDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const { data: entry, isLoading } = useDevstackEntry(id ?? '');
  const deleteEntry = useDeleteDevstackEntry();

  const [markdown, setMarkdown] = useState<string | null>(null);
  const [mdLoading, setMdLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    if (!entry?.url || entry.install_method !== 'github') return;
    const rawUrl = toRawGithubUrl(entry.url);
    setMdLoading(true);
    fetch(rawUrl)
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error(`${res.status}`))))
      .then(setMarkdown)
      .catch(() => setMarkdown(null))
      .finally(() => setMdLoading(false));
  }, [entry?.url, entry?.install_method]);

  const handleDelete = (): void => {
    if (!id) return;
    deleteEntry.mutate(id, {
      onSuccess: () => navigate('/devstack'),
    });
  };

  if (isLoading) return <LoadingSpinner />;
  if (!entry) return <p className="text-muted-foreground">Entry not found</p>;

  return (
    <div className="space-y-6">
      {/* Back + actions */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => navigate('/devstack')}>
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to catalog
        </Button>
        {canManage && (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
              <Pencil className="w-4 h-4 mr-1.5" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="w-4 h-4 mr-1.5" />
              Delete
            </Button>
          </div>
        )}
      </div>

      {/* Header card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold">{entry.name}</h1>
                {entry.featured && (
                  <Star size={18} className="text-amber-500 fill-amber-500" />
                )}
              </div>
              <p className="text-muted-foreground">{entry.description}</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{entry.type}</Badge>
                <InstallMethodBadge method={entry.install_method} iconSize={12} />
                <Badge variant="outline">{entry.origin}</Badge>
                {entry.required && (
                  <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 hover:bg-blue-100">
                    required
                  </Badge>
                )}
                {!entry.active && (
                  <Badge variant="destructive">inactive</Badge>
                )}
              </div>
              {entry.tech.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {entry.tech.map((t) => (
                    <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="text-right text-sm text-muted-foreground space-y-1 shrink-0">
              {entry.github_sha && (
                <p className="font-mono">{entry.github_sha.slice(0, 7)}</p>
              )}
              {entry.url && (
                <a
                  href={entry.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs hover:text-foreground"
                >
                  <ExternalLink size={12} /> Source
                </a>
              )}
              {entry.package && (
                <p className="text-xs">
                  {entry.package}{entry.package_version ? `@${entry.package_version}` : ''}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Markdown content */}
      {entry.install_method === 'github' && (
        <Card>
          <CardContent className="pt-6">
            {mdLoading ? (
              <LoadingSpinner />
            ) : markdown ? (
              <div data-color-mode="auto">
                <MDEditor.Markdown source={markdown} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Could not load content from source URL.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Edit form dialog */}
      {editOpen && (
        <EntryForm selectedId={entry.id} onClose={() => setEditOpen(false)} />
      )}

      {/* Delete confirmation */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete entry?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{entry.name}&quot; from the catalog.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => { e.preventDefault(); handleDelete(); }}
            >
              {deleteEntry.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
