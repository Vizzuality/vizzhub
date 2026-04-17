import { Switch } from '@/shared/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { formatDate } from '@/utils/formatters';
import { useDevstackEntries, useMyDevstackPrefs, useUpdateMyDevstackPref } from '../hooks/useDevstack';
import type { UserPref } from '../types/devstack';

function buildPrefMap(prefs: UserPref[]): Map<string, UserPref> {
  return new Map(prefs.map((p) => [p.entry_id, p]));
}

export default function MyEnvironment(): JSX.Element {
  const { data: entriesData, isLoading: entriesLoading } = useDevstackEntries({ active: true });
  const { data: prefs, isLoading: prefsLoading } = useMyDevstackPrefs();
  const updatePref = useUpdateMyDevstackPref();

  const isLoading = entriesLoading || prefsLoading;
  const entries = entriesData?.items ?? [];
  const prefMap = buildPrefMap(prefs ?? []);

  const handleToggle = (entryId: string, enabled: boolean): void => {
    updatePref.mutate({ entryId, enabled });
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">My Environment</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Enable or disable catalog entries for your personal dev environment.
          Required entries are always enabled.
        </p>
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">
          No active catalog entries available.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-20">Enabled</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Last Synced</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => {
              const pref = prefMap.get(entry.id);
              const isEnabled = entry.required || (pref?.enabled ?? false);
              const lastSynced = pref?.last_synced_at ?? null;

              return (
                <TableRow key={entry.id}>
                  <TableCell>
                    <Switch
                      checked={isEnabled}
                      disabled={entry.required}
                      onCheckedChange={(enabled) => handleToggle(entry.id, enabled)}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{entry.name}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{entry.type}</TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground max-w-[300px] truncate block">
                      {entry.description}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {lastSynced ? formatDate(lastSynced) : 'Never'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
