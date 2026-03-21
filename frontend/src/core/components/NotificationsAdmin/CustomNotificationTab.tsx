import { useEffect, useMemo, useState } from 'react';
import { useSendCustomNotification } from '../../hooks/useCustomNotification';
import { useUsers } from '../../hooks/useUsers';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { CheckCircle, Send, XCircle } from 'lucide-react';
import { getFullName } from '@/utils/formatters';
import type { User } from '@/core/types/auth';

function buildMessage(
  subject: string,
  message: string,
  linkUrl: string,
  linkText: string,
): string {
  const parts: string[] = [];
  if (subject) parts.push(`*${subject}*`);
  if (message) parts.push(message);
  if (linkUrl) {
    parts.push(linkText ? `<${linkUrl}|${linkText}>` : linkUrl);
  }
  return parts.join('\n');
}

export default function CustomNotificationTab(): JSX.Element {
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkText, setLinkText] = useState('');
  const [unfurlLinks, setUnfurlLinks] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const { data: users, isLoading: usersLoading } = useUsers();
  const sendNotification = useSendCustomNotification();

  const slackUsers = useMemo(
    () => (users ?? []).filter((u: User) => u.slack_user_id && u.active),
    [users],
  );

  const selectedUser = useMemo(
    () => slackUsers.find((u: User) => u.id === selectedUserId) ?? null,
    [slackUsers, selectedUserId],
  );

  const preview = buildMessage(subject, message, linkUrl, linkText);
  const canSend = !!selectedUser && !!preview.trim();

  useEffect(() => {
    setSendResult(null);
  }, [subject, message, linkUrl, linkText, selectedUserId, unfurlLinks]);

  const handleSend = async (): Promise<void> => {
    if (!canSend || !selectedUser) return;
    setSendResult(null);

    const result = await sendNotification.mutateAsync({
      slack_user_id: selectedUser.slack_user_id!,
      message: preview,
      unfurl_links: unfurlLinks,
    });

    setSendResult({
      ok: result.ok,
      message: result.ok ? result.message : result.error ?? 'Unknown error',
    });
  };

  if (usersLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Send Custom Notification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="subject">Subject</Label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Reminder: timesheet deadline"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="message">Message</Label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Write your message here..."
              rows={5}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="link-url">Link (optional)</Label>
            <div className="grid grid-cols-2 gap-2">
              <Input
                id="link-url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://..."
              />
              <Input
                id="link-text"
                value={linkText}
                onChange={(e) => setLinkText(e.target.value)}
                placeholder="Link text (optional)"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Send To</Label>
            <Select
              value={selectedUserId ?? ''}
              onValueChange={setSelectedUserId}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a user..." />
              </SelectTrigger>
              <SelectContent>
                {slackUsers.map((user: User) => (
                  <SelectItem key={user.id} value={user.id}>
                    {getFullName(user.first_name, user.last_name, user.email)}
                    {user.slack_display_name ? ` (@${user.slack_display_name})` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {slackUsers.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No users with Slack linked. Sync Slack profiles first.
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="unfurl-links"
              checked={unfurlLinks}
              onCheckedChange={(checked) => setUnfurlLinks(checked === true)}
            />
            <Label htmlFor="unfurl-links" className="text-sm font-normal cursor-pointer">
              Show link previews
            </Label>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={handleSend}
              disabled={!canSend || sendNotification.isPending}
            >
              <Send className="h-4 w-4 mr-2" />
              {sendNotification.isPending ? 'Sending...' : 'Send'}
            </Button>

            {sendResult && (
              <span
                className={`flex items-center gap-1 text-sm ${
                  sendResult.ok ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {sendResult.ok ? (
                  <CheckCircle className="h-4 w-4" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                {sendResult.message}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
        </CardHeader>
        <CardContent>
          {preview ? (
            <pre className="text-sm bg-muted p-4 rounded whitespace-pre-wrap font-mono min-h-[120px]">
              {preview}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">
              Type a subject and message to see the preview.
            </p>
          )}
          {selectedUser && (
            <p className="text-xs text-muted-foreground mt-3">
              Will be sent as DM to{' '}
              <span className="font-medium">
                {getFullName(selectedUser.first_name, selectedUser.last_name, selectedUser.email)}
              </span>
              {selectedUser.slack_display_name && (
                <span> (@{selectedUser.slack_display_name})</span>
              )}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
