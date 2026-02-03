import { useState } from 'react';
import { useSilences, useCreateSilence, useUpdateSilence, useDeleteSilence } from '../../hooks/useSilences';
import { useProjects } from '../../hooks/useProjects';
import { useAlertDefinitions } from '../../hooks/useAlertDefinitions';
import { formatRelativeTime } from '../../utils/dateUtils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Pencil, Trash2, Plus } from 'lucide-react';
import type { AlertSilence, AlertSilenceCreate } from '../../types';

interface SilenceFormData {
  project_id: string;
  alert_definition_id: number | null;
  silenced_until: string;
  reason: string;
}

const DEFAULT_FORM_DATA: SilenceFormData = {
  project_id: '',
  alert_definition_id: null,
  silenced_until: '',
  reason: '',
};

export default function SilencesTab(): JSX.Element {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSilence, setEditingSilence] = useState<AlertSilence | null>(null);
  const [formData, setFormData] = useState<SilenceFormData>(DEFAULT_FORM_DATA);

  const { data: silences, isLoading } = useSilences();
  const { data: projects } = useProjects();
  const { data: alertDefinitions } = useAlertDefinitions();
  const createSilence = useCreateSilence();
  const updateSilence = useUpdateSilence();
  const deleteSilence = useDeleteSilence();

  const handleOpenDialog = (silence?: AlertSilence): void => {
    if (silence) {
      setEditingSilence(silence);
      setFormData({
        project_id: silence.project_id,
        alert_definition_id: silence.alert_definition_id,
        silenced_until: silence.silenced_until?.split('T')[0] ?? '',
        reason: silence.reason ?? '',
      });
    } else {
      setEditingSilence(null);
      setFormData(DEFAULT_FORM_DATA);
    }
    setIsDialogOpen(true);
  };

  const handleCloseDialog = (): void => {
    setIsDialogOpen(false);
    setEditingSilence(null);
    setFormData(DEFAULT_FORM_DATA);
  };

  const handleSubmit = async (): Promise<void> => {
    if (editingSilence) {
      await updateSilence.mutateAsync({
        id: editingSilence.id,
        data: {
          silenced_until: formData.silenced_until ? new Date(formData.silenced_until).toISOString() : null,
          reason: formData.reason || null,
        },
      });
    } else {
      const createData: AlertSilenceCreate = {
        project_id: formData.project_id,
        alert_definition_id: formData.alert_definition_id,
        silenced_until: formData.silenced_until ? new Date(formData.silenced_until).toISOString() : null,
        reason: formData.reason || null,
      };
      await createSilence.mutateAsync(createData);
    }
    handleCloseDialog();
  };

  const handleDelete = async (id: number): Promise<void> => {
    await deleteSilence.mutateAsync(id);
  };

  const formatSilencedUntil = (dateStr: string | null): string => {
    if (!dateStr) return 'Indefinite';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Active Silences</CardTitle>
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="h-4 w-4 mr-2" />
            Add Silence
          </Button>
        </CardHeader>
        <CardContent>
          {!silences || silences.length === 0 ? (
            <p className="text-muted-foreground text-sm">No active silences.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-muted-foreground border-b">
                    <th className="pb-3 font-medium">Project</th>
                    <th className="pb-3 font-medium">Alert Type</th>
                    <th className="pb-3 font-medium">Until</th>
                    <th className="pb-3 font-medium">Reason</th>
                    <th className="pb-3 font-medium">Created</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {silences.map((silence) => (
                    <tr key={silence.id} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 text-sm">
                        {silence.project_name ?? 'Unknown'}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {silence.alert_name ?? 'All Alerts'}
                      </td>
                      <td className="py-3 pr-4 text-sm">
                        {formatSilencedUntil(silence.silenced_until)}
                      </td>
                      <td className="py-3 pr-4 text-sm max-w-xs truncate" title={silence.reason ?? undefined}>
                        {silence.reason ?? '-'}
                      </td>
                      <td className="py-3 pr-4 text-sm text-muted-foreground">
                        {formatRelativeTime(silence.created_at)}
                      </td>
                      <td className="py-3">
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenDialog(silence)}
                            title="Edit silence"
                          >
                            <Pencil className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(silence.id)}
                            disabled={deleteSilence.isPending}
                            title="Remove silence"
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingSilence ? 'Edit Silence' : 'Add Silence'}</DialogTitle>
            <DialogDescription>
              {editingSilence
                ? 'Update the silence duration and reason.'
                : 'Create a new silence to temporarily mute alerts for a project.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {!editingSilence && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="project">Project</Label>
                  <Select
                    value={formData.project_id}
                    onValueChange={(value) => setFormData((prev) => ({ ...prev, project_id: value }))}
                  >
                    <SelectTrigger id="project">
                      <SelectValue placeholder="Select a project" />
                    </SelectTrigger>
                    <SelectContent>
                      {projects?.map((project) => (
                        <SelectItem key={project.id} value={project.id}>
                          {project.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="alert-type">Alert Type (optional)</Label>
                  <Select
                    value={formData.alert_definition_id?.toString() ?? 'all'}
                    onValueChange={(value) =>
                      setFormData((prev) => ({
                        ...prev,
                        alert_definition_id: value === 'all' ? null : parseInt(value, 10),
                      }))
                    }
                  >
                    <SelectTrigger id="alert-type">
                      <SelectValue placeholder="All alert types" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Alert Types</SelectItem>
                      {alertDefinitions?.map((alert) => (
                        <SelectItem key={alert.id} value={alert.id.toString()}>
                          {alert.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="silenced-until">Silenced Until (leave empty for indefinite)</Label>
              <Input
                id="silenced-until"
                type="date"
                value={formData.silenced_until}
                onChange={(e) => setFormData((prev) => ({ ...prev, silenced_until: e.target.value }))}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="reason">Reason</Label>
              <Textarea
                id="reason"
                value={formData.reason}
                onChange={(e) => setFormData((prev) => ({ ...prev, reason: e.target.value }))}
                placeholder="Optional reason for silencing"
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={
                (!editingSilence && !formData.project_id) ||
                createSilence.isPending ||
                updateSilence.isPending
              }
            >
              {editingSilence ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
