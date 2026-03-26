import { useMemo, useState } from 'react';
import {
  useAlertDefinitions,
  useUpdateAlertDefinition,
  useAlertTemplates,
  useUpdateMessageTemplate,
  useTestAlert,
} from '../../hooks/useAlertDefinitions';
import { useUsers } from '../../hooks/useUsers';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Switch } from '@/shared/components/ui/switch';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import { FileText, Settings, Play, CheckCircle, XCircle, User, Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getFullName } from '@/utils/formatters';
import type { AlertDefinition, MessageTemplate } from '@/types';
import type { User as UserType } from '@/core/types/auth';

interface ThresholdEntry {
  key: string;
  value: string;
}

function getCategoryBadge(category: string): JSX.Element {
  return (
    <Badge variant={category === 'business' ? 'default' : 'secondary'}>
      {category}
    </Badge>
  );
}

const SCHEDULE_LABELS: Record<string, string> = {
  event: 'Event',
  daily: 'Daily',
  daily_check_monthly_report: 'Daily Check / Monthly Report',
};

function getScheduleBadge(schedule: string): JSX.Element {
  const label = SCHEDULE_LABELS[schedule] ?? schedule;
  return <Badge variant="outline">{label}</Badge>;
}

function hasRecipientConfig(configJson: Record<string, unknown>): boolean {
  return 'recipient_slack_user_id' in configJson;
}

function hasThresholdEntries(configJson: Record<string, unknown>): boolean {
  return Object.keys(configJson).some((k) => k !== 'recipient_slack_user_id');
}


function configToEntries(configJson: Record<string, unknown>): ThresholdEntry[] {
  return Object.entries(configJson).map(([key, value]) => ({
    key,
    value: String(value),
  }));
}

function entriesToConfig(entries: ThresholdEntry[]): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  for (const entry of entries) {
    const numValue = Number(entry.value);
    if (!Number.isNaN(numValue) && entry.value.trim() !== '') {
      config[entry.key] = numValue;
    } else if (entry.value === 'true') {
      config[entry.key] = true;
    } else if (entry.value === 'false') {
      config[entry.key] = false;
    } else {
      try {
        config[entry.key] = JSON.parse(entry.value);
      } catch {
        config[entry.key] = entry.value;
      }
    }
  }
  return config;
}

export default function AlertConfigTab(): JSX.Element {
  const [templateDialogAlert, setTemplateDialogAlert] = useState<AlertDefinition | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<MessageTemplate | null>(null);
  const [templateContent, setTemplateContent] = useState('');

  const [thresholdsDialogAlert, setThresholdsDialogAlert] = useState<AlertDefinition | null>(null);
  const [thresholdEntries, setThresholdEntries] = useState<ThresholdEntry[]>([]);

  const [recipientDialogAlert, setRecipientDialogAlert] = useState<AlertDefinition | null>(null);
  const [selectedRecipient, setSelectedRecipient] = useState<string>('');
  const [recipientComboOpen, setRecipientComboOpen] = useState(false);

  const [testResult, setTestResult] = useState<{
    alertId: number;
    ok: boolean;
    message: string;
  } | null>(null);

  const { data: alertDefinitions, isLoading } = useAlertDefinitions();
  const { data: allUsers } = useUsers();
  const updateAlert = useUpdateAlertDefinition();
  const { data: templates, isLoading: templatesLoading } = useAlertTemplates(
    templateDialogAlert?.id ?? null
  );
  const updateTemplate = useUpdateMessageTemplate();
  const testAlert = useTestAlert();

  const handleToggleEnabled = async (alert: AlertDefinition): Promise<void> => {
    await updateAlert.mutateAsync({
      id: alert.id,
      data: { is_enabled: !alert.is_enabled },
    });
  };

  const handleOpenTemplateDialog = (alert: AlertDefinition): void => {
    setTemplateDialogAlert(alert);
  };

  const handleCloseTemplateDialog = (): void => {
    setTemplateDialogAlert(null);
    setEditingTemplate(null);
    setTemplateContent('');
  };

  const handleEditTemplate = (template: MessageTemplate): void => {
    setEditingTemplate(template);
    setTemplateContent(template.message_template);
  };

  const handleSaveTemplate = async (): Promise<void> => {
    if (!editingTemplate) return;
    await updateTemplate.mutateAsync({
      templateId: editingTemplate.id,
      data: { message_template: templateContent },
    });
    setEditingTemplate(null);
    setTemplateContent('');
  };

  const handleCancelTemplateEdit = (): void => {
    setEditingTemplate(null);
    setTemplateContent('');
  };

  const handleOpenThresholdsDialog = (alert: AlertDefinition): void => {
    setThresholdsDialogAlert(alert);
    setThresholdEntries(configToEntries(alert.config_json));
  };

  const handleCloseThresholdsDialog = (): void => {
    setThresholdsDialogAlert(null);
    setThresholdEntries([]);
  };

  const handleThresholdChange = (index: number, value: string): void => {
    setThresholdEntries((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], value };
      return updated;
    });
  };

  const handleSaveThresholds = async (): Promise<void> => {
    if (!thresholdsDialogAlert) return;
    const newConfig = entriesToConfig(thresholdEntries);
    await updateAlert.mutateAsync({
      id: thresholdsDialogAlert.id,
      data: { config_json: newConfig },
    });
    handleCloseThresholdsDialog();
  };

  const slackUsers = useMemo(
    () => (allUsers ?? [])
      .filter((u: UserType) => u.slack_user_id && u.active)
      .sort((a, b) =>
        getFullName(a.first_name, a.last_name, a.email)
          .localeCompare(getFullName(b.first_name, b.last_name, b.email)),
      ),
    [allUsers],
  );

  const handleOpenRecipientDialog = (alert: AlertDefinition): void => {
    setRecipientDialogAlert(alert);
    setSelectedRecipient(
      (alert.config_json as Record<string, string>).recipient_slack_user_id ?? '',
    );
  };

  const handleCloseRecipientDialog = (): void => {
    setRecipientDialogAlert(null);
    setSelectedRecipient('');
  };

  const handleSaveRecipient = async (): Promise<void> => {
    if (!recipientDialogAlert) return;
    await updateAlert.mutateAsync({
      id: recipientDialogAlert.id,
      data: {
        config_json: {
          ...recipientDialogAlert.config_json,
          recipient_slack_user_id: selectedRecipient,
        },
      },
    });
    handleCloseRecipientDialog();
  };

  const getRecipientName = (alert: AlertDefinition): string | null => {
    const slackId = (alert.config_json as Record<string, string>).recipient_slack_user_id;
    if (!slackId) return null;
    const user = (allUsers ?? []).find((u: UserType) => u.slack_user_id === slackId);
    return user ? getFullName(user.first_name, user.last_name, user.email) : slackId;
  };

  const handleTestAlert = async (alert: AlertDefinition): Promise<void> => {
    setTestResult(null);
    const result = await testAlert.mutateAsync(alert.id);
    setTestResult({
      alertId: alert.id,
      ok: result.ok,
      message: result.ok ? result.message : result.error ?? 'Unknown error',
    });
    setTimeout(() => {
      setTestResult(null);
    }, 5000);
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Alert Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          {!alertDefinitions || alertDefinitions.length === 0 ? (
            <p className="text-muted-foreground text-sm">No alert definitions found.</p>
          ) : (
            <div className="space-y-4">
              {alertDefinitions.map((alert) => (
                <div
                  key={alert.id}
                  className="flex items-center justify-between p-4 border rounded-lg"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{alert.name}</h3>
                      {getCategoryBadge(alert.category)}
                      {getScheduleBadge(alert.schedule)}
                    </div>
                    {alert.description && (
                      <p className="text-sm text-muted-foreground">{alert.description}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Channel: {alert.channel_type === 'leadership' ? 'Leadership' : 'Project'}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {testResult?.alertId === alert.id && (
                      <span
                        className={`flex items-center gap-1 text-sm ${
                          testResult.ok ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {testResult.ok ? (
                          <CheckCircle className="h-4 w-4" />
                        ) : (
                          <XCircle className="h-4 w-4" />
                        )}
                        {testResult.message}
                      </span>
                    )}

                    <div className="flex items-center gap-2">
                      <Switch
                        checked={alert.is_enabled}
                        onCheckedChange={() => handleToggleEnabled(alert)}
                        disabled={updateAlert.isPending}
                      />
                      <span className="text-sm text-muted-foreground">
                        {alert.is_enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>

                    {hasRecipientConfig(alert.config_json) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenRecipientDialog(alert)}
                      >
                        <User className="h-4 w-4 mr-2" />
                        {getRecipientName(alert) ?? 'Recipient'}
                      </Button>
                    )}

                    {hasThresholdEntries(alert.config_json) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenThresholdsDialog(alert)}
                      >
                        <Settings className="h-4 w-4 mr-2" />
                        Thresholds
                      </Button>
                    )}

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenTemplateDialog(alert)}
                    >
                      <FileText className="h-4 w-4 mr-2" />
                      Templates
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleTestAlert(alert)}
                      disabled={testAlert.isPending}
                    >
                      <Play className="h-4 w-4 mr-2" />
                      Test
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Template Dialog */}
      <Dialog
        open={templateDialogAlert !== null}
        onOpenChange={(open) => !open && handleCloseTemplateDialog()}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Message Templates - {templateDialogAlert?.name}</DialogTitle>
            <DialogDescription>
              Edit the message templates for this alert type. Templates support variables like{' '}
              {'{project_name}'}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4 max-h-96 overflow-y-auto">
            {templatesLoading && <LoadingSpinner />}
            {!templatesLoading && (!templates || templates.length === 0) && (
              <p className="text-muted-foreground text-sm">
                No templates configured for this alert.
              </p>
            )}
            {!templatesLoading && templates && templates.length > 0 &&
              templates.map((template) => (
                <div key={template.id} className="space-y-2 p-3 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Label className="font-medium capitalize">{template.template_type}</Label>
                      <Badge variant={template.is_active ? 'default' : 'secondary'}>
                        {template.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                    {editingTemplate?.id !== template.id && (
                      <Button variant="ghost" size="sm" onClick={() => handleEditTemplate(template)}>
                        Edit
                      </Button>
                    )}
                  </div>

                  {editingTemplate?.id === template.id ? (
                    <div className="space-y-2">
                      <Textarea
                        value={templateContent}
                        onChange={(e) => setTemplateContent(e.target.value)}
                        rows={4}
                        className="font-mono text-sm"
                      />
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={handleCancelTemplateEdit}>
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          onClick={handleSaveTemplate}
                          disabled={updateTemplate.isPending}
                        >
                          Save
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <pre className="text-sm bg-muted p-2 rounded whitespace-pre-wrap font-mono">
                      {template.message_template}
                    </pre>
                  )}
                </div>
              ))}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseTemplateDialog}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Thresholds Dialog */}
      <Dialog
        open={thresholdsDialogAlert !== null}
        onOpenChange={(open) => !open && handleCloseThresholdsDialog()}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Thresholds - {thresholdsDialogAlert?.name}</DialogTitle>
            <DialogDescription>
              Configure the threshold values for this alert type.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {thresholdEntries.length === 0 ? (
              <p className="text-muted-foreground text-sm">No thresholds configured.</p>
            ) : (
              thresholdEntries.map((entry, index) => (
                <div key={entry.key} className="space-y-2">
                  <Label htmlFor={`threshold-${entry.key}`} className="font-medium">
                    {entry.key.replaceAll('_', ' ').replaceAll(/\b\w/g, (c: string) => c.toUpperCase())}
                  </Label>
                  <Input
                    id={`threshold-${entry.key}`}
                    value={entry.value}
                    onChange={(e) => handleThresholdChange(index, e.target.value)}
                    className="font-mono"
                  />
                </div>
              ))
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseThresholdsDialog}>
              Cancel
            </Button>
            <Button onClick={handleSaveThresholds} disabled={updateAlert.isPending}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Recipient Dialog */}
      <Dialog
        open={recipientDialogAlert !== null}
        onOpenChange={(open) => !open && handleCloseRecipientDialog()}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Select Recipient</DialogTitle>
            <DialogDescription>
              Choose which user receives Slack notifications for this alert.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <Label className="font-medium mb-2 block">User</Label>
            <Popover open={recipientComboOpen} onOpenChange={setRecipientComboOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={recipientComboOpen}
                  className="w-full justify-between font-normal"
                >
                  <span className="truncate">
                    {selectedRecipient
                      ? (() => {
                          const u = slackUsers.find((u: UserType) => u.slack_user_id === selectedRecipient);
                          return u ? getFullName(u.first_name, u.last_name, u.email) : selectedRecipient;
                        })()
                      : 'Select a user...'}
                  </span>
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                <Command>
                  <CommandInput placeholder="Search users..." />
                  <CommandList>
                    <CommandEmpty>No user found.</CommandEmpty>
                    <CommandGroup>
                      {slackUsers.map((u: UserType) => {
                        const name = getFullName(u.first_name, u.last_name, u.email);
                        return (
                          <CommandItem
                            key={u.id}
                            value={name}
                            onSelect={() => {
                              setSelectedRecipient(u.slack_user_id!);
                              setRecipientComboOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                'mr-2 h-4 w-4',
                                selectedRecipient === u.slack_user_id ? 'opacity-100' : 'opacity-0',
                              )}
                            />
                            {name}
                            {u.slack_display_name ? ` (@${u.slack_display_name})` : ''}
                          </CommandItem>
                        );
                      })}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            {slackUsers.length === 0 && (
              <p className="text-muted-foreground text-sm mt-2">
                No active users with Slack linked.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseRecipientDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveRecipient}
              disabled={updateAlert.isPending || !selectedRecipient}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
