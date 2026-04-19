import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Pencil, Star, Trash2 } from 'lucide-react';
import MDEditor from '@uiw/react-md-editor';
import { useTheme } from 'next-themes';
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
import {
  useDevstackEntry,
  useDeleteDevstackEntry,
  useDevstackEntryContent,
} from '../hooks/useDevstack';
import { EntryForm } from '../components/EntryForm';
import { InstallMethodBadge } from '../components/EntryBadges';

interface MarkdownContentProps {
  mdLoading: boolean;
  markdown: string | null;
  mdError: boolean;
  resolvedTheme: string | undefined;
}

function renderMarkdownContent({
  mdLoading,
  markdown,
  mdError,
  resolvedTheme,
}: MarkdownContentProps): JSX.Element {
  if (mdLoading) return <LoadingSpinner />;
  if (!markdown || mdError) {
    return (
      <p className="text-sm text-muted-foreground">
        Could not load content from source URL.
      </p>
    );
  }
  return (
    <div data-color-mode={resolvedTheme === 'dark' ? 'dark' : 'light'}>
      <MDEditor.Markdown source={markdown} />
    </div>
  );
}

function formatRelative(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export default function EntryDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const canManage = usePermission(Action.DEVSTACK_MANAGE);
  const { resolvedTheme } = useTheme();
  const { data: entry, isLoading } = useDevstackEntry(id ?? '');
  const deleteEntry = useDeleteDevstackEntry();

  const isGithubEntry = entry?.install_method === 'github';
  const {
    data: contentData,
    isLoading: mdLoading,
    isError: mdError,
  } = useDevstackEntryContent(id ?? '', isGithubEntry);
  const markdown = contentData?.content
    ? contentData.content.replace(/^---\n[\s\S]*?\n---\n?/, '')
    : null;

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

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
              <div
                data-color-mode={resolvedTheme === 'dark' ? 'dark' : 'light'}
                className="text-muted-foreground text-sm"
              >
                <MDEditor.Markdown
                  source={entry.description}
                  style={{ background: 'transparent' }}
                />
              </div>
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
              {entry.install_method === 'npm' &&
               entry.latest_package_version &&
               entry.latest_package_version !== entry.package_version && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Latest: {entry.latest_package_version}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {entry.deprecated && (
        <Card className="border-amber-500/40 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="pt-6">
            <p className="font-semibold text-amber-900 dark:text-amber-100">
              Deprecated
            </p>
            {entry.deprecation_message && (
              <p className="text-sm text-amber-800 dark:text-amber-200 mt-1">
                {entry.deprecation_message}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {entry.vulnerabilities && entry.vulnerabilities.advisories.length > 0 && (
        <Card className="border-red-500/40">
          <CardContent className="pt-6 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Security advisories</h2>
              <div className="flex gap-2 text-xs">
                {(['critical', 'high', 'moderate', 'low'] as const).map((sev) => {
                  const count = entry.vulnerabilities![sev];
                  if (count === 0) return null;
                  return (
                    <Badge key={sev} variant="outline" className="capitalize">
                      {count} {sev}
                    </Badge>
                  );
                })}
              </div>
            </div>
            <ul className="space-y-2">
              {entry.vulnerabilities.advisories.map((a) => (
                <li key={a.id} className="flex items-start gap-3 text-sm">
                  <Badge
                    variant="outline"
                    className="capitalize shrink-0 mt-0.5"
                  >
                    {a.severity}
                  </Badge>
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 hover:underline"
                  >
                    <span className="font-mono text-xs text-muted-foreground mr-2">
                      {a.id}
                    </span>
                    {a.title}
                  </a>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground flex flex-wrap gap-x-6 gap-y-1">
          <span>Installed {entry.install_count} times</span>
          <span>Last install: {formatRelative(entry.last_installed_at)}</span>
        </CardContent>
      </Card>

      {/* Markdown content */}
      {entry.install_method === 'github' && (
        <Card>
          <CardContent className="pt-6">
            {renderMarkdownContent({
              mdLoading,
              markdown,
              mdError,
              resolvedTheme,
            })}
          </CardContent>
        </Card>
      )}

      {/* Edit form dialog */}
      {canManage && editOpen && (
        <EntryForm selectedId={entry.id} onClose={() => setEditOpen(false)} />
      )}

      {/* Delete confirmation */}
      <AlertDialog
        open={canManage && deleteOpen}
        onOpenChange={setDeleteOpen}
      >
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
