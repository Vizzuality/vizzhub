import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Trash2, PauseCircle, CheckCircle2, RotateCcw, Calendar, AlertTriangle, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
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
import { cn } from '@/lib/utils';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Can, Action, usePermission } from '@/core/permissions';
import { useAuth } from '@/core/hooks/useAuth';
import { formatCurrency } from '@/shared/utils/evmCalculations';
import {
  useCreateInvoice,
  useTransitionInvoice,
  useDeleteInvoice,
} from '../hooks/useInvoices';
import { trackerApi } from '../services/tracker';
import {
  EditableCell,
  STATUS_LABELS,
  STATUS_DOT_COLORS,
  useInvoiceFieldSave,
  getDisplayDate,
} from './invoice-shared';
import type {
  Invoice,
  AdminInvoice,
  InvoiceCreate,
  InvoiceStatus,
  Postponement,
} from '../types/tracker';

type InvoiceLike = Invoice | AdminInvoice;

interface InvoiceDetailContentProps {
  readonly invoice?: InvoiceLike;
  readonly projectId: string;
  readonly currency: string;
  readonly projectName?: string;
  readonly onClose?: () => void;
  readonly onCreated?: (invoiceId: string) => void;
  readonly onDeleted?: () => void;
}

const STATUS_DESCRIPTIONS: Record<InvoiceStatus, (inv: InvoiceLike) => string> = {
  scheduled: (inv) => `Scheduled to issue on ${inv.due_date}. Will move to "Pending" automatically when the date arrives.`,
  pending_to_issue: () => 'Ready to send to the client. When issued, mark as invoiced.',
  postpone_pending: () => 'A postpone request is waiting for admin approval. The original due date still applies until it is decided.',
  postponed: (inv) => inv.postponed_to
    ? `Postponed to ${inv.postponed_to}. Remove the latest postponement to re-open.`
    : 'Postponed.',
  waiting_for_payment: (inv) => inv.invoiced_on
    ? `Sent on ${inv.invoiced_on}. Awaiting client transfer.`
    : 'Sent to the client. Awaiting transfer.',
  paid: (inv) => inv.invoiced_on
    ? `Paid. Invoiced on ${inv.invoiced_on}.`
    : 'Paid.',
};

function daysRemaining(dateStr: string): { label: string; tone: 'ok' | 'warn' | 'danger' } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${dateStr}T00:00:00`);
  const diff = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff < 0) return { label: `${Math.abs(diff)}d overdue`, tone: 'danger' };
  if (diff === 0) return { label: 'Due today', tone: 'danger' };
  if (diff <= 7) return { label: `${diff}d remaining`, tone: 'warn' };
  return { label: `${diff}d remaining`, tone: 'ok' };
}

const TONE_CLASS = {
  ok: 'text-muted-foreground',
  warn: 'text-aux-amber',
  danger: 'text-aux-red',
} as const;

function Section({
  title,
  children,
  action,
}: {
  readonly title: string;
  readonly children: React.ReactNode;
  readonly action?: React.ReactNode;
}): JSX.Element {
  return (
    <Card>
      <CardContent className="pt-4 pb-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {title}
          </h3>
          {action}
        </div>
        {children}
      </CardContent>
    </Card>
  );
}

function FieldRow({
  label,
  children,
  hint,
}: {
  readonly label: string;
  readonly children: React.ReactNode;
  readonly hint?: React.ReactNode;
}): JSX.Element {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-sm items-baseline">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-baseline gap-2 flex-wrap">
        <div>{children}</div>
        {hint}
      </div>
    </div>
  );
}

function StatusBlock({
  invoice,
  onError,
  onMutated,
  canManage,
}: {
  readonly invoice: InvoiceLike;
  readonly onError: (msg: string) => void;
  readonly onMutated: () => void;
  readonly canManage: boolean;
}): JSX.Element {
  const transition = useTransitionInvoice(invoice.project_id);
  const [postponeOpen, setPostponeOpen] = useState(false);
  const [issueEarlyOpen, setIssueEarlyOpen] = useState(false);

  const handleTransition = (next: InvoiceStatus): void => {
    transition.mutate(
      { invoiceId: invoice.id, status: next },
      {
        onSuccess: () => { setIssueEarlyOpen(false); onMutated(); },
        onError: (err: unknown) => {
          const msg = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail ?? 'Transition failed';
          onError(msg);
        },
      },
    );
  };

  const status = invoice.status;
  const description = STATUS_DESCRIPTIONS[status]?.(invoice) ?? '';

  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        <div className="flex items-start gap-3">
          <span className={cn('inline-block w-2.5 h-2.5 rounded-full mt-1.5 shrink-0', STATUS_DOT_COLORS[status])} />
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm">{STATUS_LABELS[status]}</div>
            <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
          </div>
        </div>

        {canManage && (
          <div className="flex flex-wrap gap-2 mt-3">
            {status === 'pending_to_issue' && (
              <Button
                size="sm"
                className="h-8"
                disabled={transition.isPending}
                onClick={() => handleTransition('waiting_for_payment')}
              >
                <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                Mark as invoiced
              </Button>
            )}
            {status === 'scheduled' && (
              <AlertDialog open={issueEarlyOpen} onOpenChange={setIssueEarlyOpen}>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="outline" className="h-8">
                    <AlertTriangle className="w-3.5 h-3.5 mr-1.5 text-aux-amber" />
                    Issue now
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Issue invoice before scheduled date?</AlertDialogTitle>
                    <AlertDialogDescription>
                      The scheduled date ({invoice.due_date}) hasn&rsquo;t arrived yet.
                      Invoices normally move to &ldquo;Pending&rdquo; automatically
                      when their date arrives. Issue early only if you need to send
                      it to the client ahead of schedule.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={(e) => {
                        e.preventDefault();
                        handleTransition('waiting_for_payment');
                      }}
                      disabled={transition.isPending}
                    >
                      Issue now
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
            {(status === 'scheduled' || status === 'pending_to_issue') && (
              <PostponeAction
                invoice={invoice}
                open={postponeOpen}
                onOpenChange={setPostponeOpen}
                onError={onError}
                onSuccess={onMutated}
              />
            )}
            {status === 'waiting_for_payment' && (
              <>
                <Button
                  size="sm"
                  className="h-8"
                  disabled={transition.isPending}
                  onClick={() => handleTransition('paid')}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  Mark as paid
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  disabled={transition.isPending}
                  onClick={() => handleTransition('pending_to_issue')}
                >
                  <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                  Revert to pending
                </Button>
              </>
            )}
            {status === 'paid' && (
              <Button
                size="sm"
                variant="outline"
                className="h-8"
                disabled={transition.isPending}
                onClick={() => handleTransition('waiting_for_payment')}
              >
                <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                Revert to waiting
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PostponeAction({
  invoice,
  open,
  onOpenChange,
  onError,
  onSuccess,
}: {
  readonly invoice: InvoiceLike;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onError: (msg: string) => void;
  readonly onSuccess: () => void;
}): JSX.Element {
  const [newDate, setNewDate] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const baseDate = invoice.postponed_to ?? invoice.due_date;
  const base = new Date(`${baseDate}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const maxRef = base > today ? base : today;
  const minDate = new Date(maxRef);
  minDate.setDate(minDate.getDate() + 1);
  const maxDate = new Date(maxRef);
  maxDate.setDate(maxDate.getDate() + 30);
  const fmt = (d: Date): string => d.toISOString().split('T')[0];

  const handlePostpone = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault();
    if (!newDate || !reason.trim()) return;
    setSubmitting(true);
    try {
      await trackerApi.postponeInvoice(invoice.project_id, invoice.id, {
        postponed_to: newDate,
        reason: reason.trim(),
      });
      onOpenChange(false);
      setNewDate('');
      setReason('');
      onSuccess();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Postpone failed';
      onError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogTrigger asChild>
        <Button size="sm" variant="outline" className="h-8">
          <PauseCircle className="w-3.5 h-3.5 mr-1.5" />
          Request postpone
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Request postpone</AlertDialogTitle>
          <AlertDialogDescription>
            Maximum 30 days from {fmt(maxRef)}. An admin will be notified on Slack
            and the new date takes effect only after approval.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3 py-2">
          <Input
            type="date"
            value={newDate}
            min={fmt(minDate)}
            max={fmt(maxDate)}
            onChange={(e) => setNewDate(e.target.value)}
            className="h-9 text-sm"
          />
          <Textarea
            placeholder="Reason for postponement..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="text-sm min-h-[80px]"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handlePostpone}
            disabled={submitting || !newDate || !reason.trim()}
          >
            Send request
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function PendingRequestBlock({
  invoice,
  pending,
  onMutated,
  onError,
  canApprove,
  canCancel,
}: {
  readonly invoice: InvoiceLike;
  readonly pending: Postponement;
  readonly onMutated: () => void;
  readonly onError: (msg: string) => void;
  readonly canApprove: boolean;
  readonly canCancel: boolean;
}): JSX.Element {
  const [submitting, setSubmitting] = useState(false);
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [rejectNote, setRejectNote] = useState('');

  const handleApiCall = async (
    action: 'approve' | 'reject' | 'cancel',
    closeDialog: () => void,
  ): Promise<void> => {
    setSubmitting(true);
    try {
      if (action === 'approve') {
        await trackerApi.approvePostponement(invoice.project_id, invoice.id, pending.id);
      } else if (action === 'reject') {
        await trackerApi.rejectPostponement(invoice.project_id, invoice.id, pending.id, {
          note: rejectNote.trim(),
        });
        setRejectNote('');
      } else {
        await trackerApi.cancelPostponement(invoice.project_id, invoice.id, pending.id);
      }
      closeDialog();
      onMutated();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? `${action} failed`;
      onError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="border-blue-500/40">
      <CardContent className="pt-4 pb-4">
        <div className="flex items-start gap-3">
          <span className={cn('inline-block w-2.5 h-2.5 rounded-full mt-1.5 shrink-0', STATUS_DOT_COLORS.postpone_pending)} />
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm">{STATUS_LABELS.postpone_pending}</div>
            <p className="text-sm text-muted-foreground mt-0.5">
              {STATUS_DESCRIPTIONS.postpone_pending(invoice)}
            </p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-sm">
          <span className="text-muted-foreground">Proposed</span>
          <span className="tabular-nums">
            {pending.postponed_to}
            <span className="text-xs text-muted-foreground ml-2">
              ← from {invoice.due_date}
            </span>
          </span>
          <span className="text-muted-foreground">Reason</span>
          <span>&ldquo;{pending.reason}&rdquo;</span>
          <span className="text-muted-foreground">Requested by</span>
          <span>
            {pending.created_by_name ?? 'Unknown'}
            <span className="text-xs text-muted-foreground ml-2">
              {new Date(pending.created_at).toLocaleDateString()}
            </span>
          </span>
        </div>

        {(canApprove || canCancel) && (
          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t">
            {canApprove && (
              <>
                <AlertDialog open={approveOpen} onOpenChange={setApproveOpen}>
                  <AlertDialogTrigger asChild>
                    <Button size="sm" className="h-8">
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                      Approve
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Approve postpone request?</AlertDialogTitle>
                      <AlertDialogDescription>
                        The invoice due date will move to {pending.postponed_to}.
                        The requester will be notified on Slack.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={(e) => { e.preventDefault(); handleApiCall('approve', () => setApproveOpen(false)); }}
                        disabled={submitting}
                      >
                        Approve
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
                <AlertDialog open={rejectOpen} onOpenChange={setRejectOpen}>
                  <AlertDialogTrigger asChild>
                    <Button size="sm" variant="outline" className="h-8 text-destructive">
                      <X className="w-3.5 h-3.5 mr-1.5" />
                      Reject
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Reject postpone request?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Provide a reason — it will be sent to the requester on Slack.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <Textarea
                      placeholder="Reason for rejection..."
                      value={rejectNote}
                      onChange={(e) => setRejectNote(e.target.value)}
                      className="text-sm min-h-[80px]"
                    />
                    <AlertDialogFooter>
                      <AlertDialogCancel onClick={() => setRejectNote('')}>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={(e) => { e.preventDefault(); handleApiCall('reject', () => setRejectOpen(false)); }}
                        disabled={submitting || !rejectNote.trim()}
                      >
                        Reject
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </>
            )}
            {canCancel && (
              <AlertDialog open={cancelOpen} onOpenChange={setCancelOpen}>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="ghost" className="h-8 ml-auto text-muted-foreground">
                    Cancel request
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Cancel postpone request?</AlertDialogTitle>
                    <AlertDialogDescription>
                      The request will be withdrawn. The approver will be notified on Slack.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Keep request</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={(e) => { e.preventDefault(); handleApiCall('cancel', () => setCancelOpen(false)); }}
                      disabled={submitting}
                    >
                      Cancel request
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PostponementTimeline({
  postponements,
  invoice,
  onMutated,
  canManage,
}: {
  readonly postponements: readonly Postponement[];
  readonly invoice: InvoiceLike;
  readonly onMutated: () => void;
  readonly canManage: boolean;
}): JSX.Element {
  const [deleting, setDeleting] = useState(false);
  const [open, setOpen] = useState(false);

  const handleDelete = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault();
    setDeleting(true);
    try {
      await trackerApi.deleteLatestPostponement(invoice.project_id, invoice.id);
      onMutated();
      setOpen(false);
    } finally {
      setDeleting(false);
    }
  };

  const approvedOnly = postponements.filter((p) => p.approval_status === 'approved');
  const ordered = [...approvedOnly].reverse();

  return (
    <ol className="space-y-3 text-sm">
      <li className="flex items-start gap-3">
        <span className="inline-block w-2 h-2 rounded-full bg-muted-foreground mt-1.5 shrink-0" />
        <div>
          <div className="tabular-nums">{invoice.due_date}</div>
          <div className="text-xs text-muted-foreground">Original due date</div>
        </div>
      </li>
      {ordered.map((p, idx) => {
        const isLatest = idx === ordered.length - 1;
        const prevDate = idx === 0 ? invoice.due_date : ordered[idx - 1].postponed_to;
        return (
          <li key={p.id} className="flex items-start gap-3">
            <span className="inline-block w-2 h-2 rounded-full bg-orange-400 mt-1.5 shrink-0" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="tabular-nums">{p.postponed_to}</span>
                <span className="text-xs text-muted-foreground">← from {prevDate}</span>
              </div>
              <div className="text-xs text-foreground mt-0.5">&ldquo;{p.reason}&rdquo;</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {p.created_by_name ? `by ${p.created_by_name} · ` : ''}
                {new Date(p.created_at).toLocaleDateString()}
              </div>
            </div>
            {isLatest && canManage && (
              <AlertDialog open={open} onOpenChange={setOpen}>
                <AlertDialogTrigger asChild>
                  <button
                    className="text-muted-foreground hover:text-destructive transition-colors p-0.5 shrink-0"
                    title="Remove latest postponement"
                    disabled={deleting}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Remove last postponement?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Revert to {prevDate}. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      onClick={handleDelete}
                      disabled={deleting}
                    >
                      Remove
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function DeleteAction({
  invoice,
  currency,
  onSuccess,
}: {
  readonly invoice: InvoiceLike;
  readonly currency: string;
  readonly onSuccess: () => void;
}): JSX.Element {
  const mutation = useDeleteInvoice(invoice.project_id);
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive hover:bg-destructive/10"
        >
          <Trash2 className="w-3.5 h-3.5 mr-1.5" />
          Delete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete invoice?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete &ldquo;{invoice.milestone}&rdquo;
            ({formatCurrency(invoice.amount, currency, 2)}). This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={() => mutation.mutate(invoice.id, { onSuccess })}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function CreateForm({
  projectId,
  projectName,
  currency,
  onCreated,
  onClose,
}: {
  readonly projectId: string;
  readonly projectName?: string;
  readonly currency: string;
  readonly onCreated?: (invoiceId: string) => void;
  readonly onClose?: () => void;
}): JSX.Element {
  const create = useCreateInvoice(projectId);
  const [form, setForm] = useState<InvoiceCreate>({
    milestone: '',
    amount: 0,
    due_date: '',
    code: '',
    observations: '',
    invoicing_contact_name: '',
    invoicing_contact_email: '',
  });
  const [error, setError] = useState<string | null>(null);

  const update = (patch: Partial<InvoiceCreate>): void => {
    setForm((prev) => ({ ...prev, ...patch }));
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!form.milestone || !form.due_date || !form.amount) {
      setError('Milestone, amount and due date are required');
      return;
    }
    setError(null);
    create.mutate(
      {
        milestone: form.milestone,
        amount: form.amount,
        due_date: form.due_date,
        code: form.code || null,
        observations: form.observations || null,
        invoicing_contact_name: form.invoicing_contact_name || null,
        invoicing_contact_email: form.invoicing_contact_email || null,
      },
      {
        onSuccess: (inv) => {
          onCreated?.(inv.id);
          onClose?.();
        },
        onError: (err: unknown) => {
          const msg = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail ?? 'Create failed';
          setError(msg);
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">New invoice</h2>
        {projectName && (
          <Link
            to={`/tracker/projects/${projectId}`}
            className="text-sm text-muted-foreground hover:underline"
          >
            {projectName}
          </Link>
        )}
      </div>

      {error && (
        <div className="px-3 py-2 rounded bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}

      <Section title="Details">
        <FieldRow label="Milestone">
          <Input
            aria-label="Milestone"
            value={form.milestone}
            onChange={(e) => update({ milestone: e.target.value })}
            className="h-8 text-sm w-full"
          />
        </FieldRow>
        <FieldRow label="Code">
          <Input
            aria-label="Code"
            value={form.code ?? ''}
            onChange={(e) => update({ code: e.target.value })}
            className="h-8 text-sm w-40"
          />
        </FieldRow>
        <FieldRow label="Amount" hint={<span className="text-xs text-muted-foreground">{currency.toUpperCase()}</span>}>
          <Input
            aria-label="Amount"
            type="number"
            min="0"
            step="0.01"
            value={form.amount || ''}
            onChange={(e) => update({ amount: Number.parseFloat(e.target.value) || 0 })}
            className="h-8 text-sm w-40 text-right"
          />
        </FieldRow>
      </Section>

      <Section title="Dates">
        <FieldRow label="Due date">
          <Input
            aria-label="Due date"
            type="date"
            value={form.due_date}
            onChange={(e) => update({ due_date: e.target.value })}
            className="h-8 text-sm w-44"
          />
        </FieldRow>
      </Section>

      <Section title="Invoicing contact">
        <FieldRow label="Name">
          <Input
            aria-label="Contact name"
            value={form.invoicing_contact_name ?? ''}
            onChange={(e) => update({ invoicing_contact_name: e.target.value })}
            className="h-8 text-sm w-full"
          />
        </FieldRow>
        <FieldRow label="Email">
          <Input
            aria-label="Contact email"
            type="email"
            value={form.invoicing_contact_email ?? ''}
            onChange={(e) => update({ invoicing_contact_email: e.target.value })}
            className="h-8 text-sm w-full"
          />
        </FieldRow>
      </Section>

      <Section title="Notes">
        <Textarea
          aria-label="Notes"
          value={form.observations ?? ''}
          onChange={(e) => update({ observations: e.target.value })}
          className="text-sm min-h-[60px]"
        />
      </Section>

      <div className="flex justify-end gap-2 pt-2">
        {onClose && (
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={create.isPending}>
          Create invoice
        </Button>
      </div>
    </form>
  );
}

function EditView({
  invoice,
  currency,
  projectName,
  onDeleted,
}: {
  readonly invoice: InvoiceLike;
  readonly currency: string;
  readonly projectName?: string;
  readonly onDeleted?: () => void;
}): JSX.Element {
  const qc = useQueryClient();
  const canManage = usePermission(Action.TRACKER_MANAGE);
  const isAdmin = usePermission('*' as never);
  const { user } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.detail(invoice.id) });
    qc.invalidateQueries({ queryKey: ['tracker', 'invoices', 'all'] });
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.totals });
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.byProject(invoice.project_id) });
    qc.invalidateQueries({ queryKey: queryKeys.tracker.invoices.postponements(invoice.project_id, invoice.id) });
  }, [qc, invoice.id, invoice.project_id]);

  const save = useInvoiceFieldSave(invoice.project_id, invoice.id, invalidate);

  const showError = useCallback((msg: string): void => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  }, []);

  const { data: postponements } = useQuery({
    queryKey: queryKeys.tracker.invoices.postponements(invoice.project_id, invoice.id),
    queryFn: () => trackerApi.listPostponements(invoice.project_id, invoice.id),
    enabled: invoice.postpone_count > 0 || invoice.status === 'postpone_pending',
  });

  const pendingRequest = postponements?.find((p) => p.approval_status === 'pending');
  const isPendingFlow = invoice.status === 'postpone_pending' && pendingRequest;

  const displayDate = getDisplayDate(invoice);
  const daysInfo = daysRemaining(displayDate);
  const showDays = invoice.status === 'pending_to_issue'
    || invoice.status === 'waiting_for_payment'
    || invoice.status === 'postponed';

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold leading-tight truncate">{invoice.milestone}</h2>
          {projectName && (
            <Link
              to={`/tracker/projects/${invoice.project_id}`}
              className="text-sm text-muted-foreground hover:underline"
            >
              {projectName}
            </Link>
          )}
        </div>
        <Can do={Action.TRACKER_MANAGE}>
          <DeleteAction
            invoice={invoice}
            currency={currency}
            onSuccess={() => {
              invalidate();
              onDeleted?.();
            }}
          />
        </Can>
      </div>

      {error && (
        <div className="px-3 py-2 rounded bg-destructive/10 text-destructive text-sm">
          {error}
        </div>
      )}

      {isPendingFlow ? (
        <PendingRequestBlock
          invoice={invoice}
          pending={pendingRequest}
          onMutated={invalidate}
          onError={showError}
          canApprove={isAdmin}
          canCancel={
            canManage && (
              isAdmin || (!!user?.id && pendingRequest.created_by === user.id)
            )
          }
        />
      ) : (
        <StatusBlock
          invoice={invoice}
          onError={showError}
          onMutated={invalidate}
          canManage={canManage}
        />
      )}

      <Section title="Details">
        <FieldRow label="Code">
          {canManage ? (
            <EditableCell
              value={invoice.code ?? ''}
              placeholder="add code"
              onSave={(v) => save('code', v)}
              inputClass="h-7 w-40 text-sm px-1"
            />
          ) : (
            <span>{invoice.code ?? '—'}</span>
          )}
        </FieldRow>
        <FieldRow label="Milestone">
          {canManage ? (
            <EditableCell
              value={invoice.milestone}
              onSave={(v) => save('milestone', v)}
              inputClass="h-7 w-full text-sm px-1"
            />
          ) : (
            <span>{invoice.milestone}</span>
          )}
        </FieldRow>
        <FieldRow label="Amount" hint={<span className="text-xs text-muted-foreground">{currency.toUpperCase()}</span>}>
          {canManage ? (
            <EditableCell
              value={invoice.amount.toString()}
              display={formatCurrency(invoice.amount, currency, 2)}
              inputType="number"
              onSave={(v) => save('amount', v)}
              inputClass="h-7 w-32 text-sm px-1"
            />
          ) : (
            <span className="tabular-nums">{formatCurrency(invoice.amount, currency, 2)}</span>
          )}
        </FieldRow>
      </Section>

      <Section title="Dates">
        <FieldRow
          label="Due date"
          hint={
            <span className="flex items-center gap-1.5 text-xs">
              {showDays && (
                <span className={cn('inline-flex items-center gap-1', TONE_CLASS[daysInfo.tone])}>
                  <Calendar className="w-3 h-3" />
                  {daysInfo.label}
                </span>
              )}
              {invoice.status === 'postponed' && invoice.postpone_count > 0 && (
                <span className="text-muted-foreground">
                  · postponed {invoice.postpone_count}× from {invoice.due_date}
                </span>
              )}
            </span>
          }
        >
          <span className="tabular-nums">{displayDate}</span>
        </FieldRow>
        {invoice.invoiced_on && (
          <FieldRow label="Invoiced on">
            <span className="tabular-nums">{invoice.invoiced_on}</span>
          </FieldRow>
        )}
      </Section>

      <Section title="Invoicing contact">
        <FieldRow label="Name">
          {canManage ? (
            <EditableCell
              value={invoice.invoicing_contact_name ?? ''}
              placeholder="add name"
              onSave={(v) => save('invoicing_contact_name', v)}
              inputClass="h-7 w-full text-sm px-1"
            />
          ) : (
            <span>{invoice.invoicing_contact_name ?? '—'}</span>
          )}
        </FieldRow>
        <FieldRow label="Email">
          {canManage ? (
            <EditableCell
              value={invoice.invoicing_contact_email ?? ''}
              placeholder="add email"
              inputType="email"
              onSave={(v) => save('invoicing_contact_email', v)}
              inputClass="h-7 w-full text-sm px-1"
            />
          ) : (
            <span>{invoice.invoicing_contact_email ?? '—'}</span>
          )}
        </FieldRow>
      </Section>

      {(invoice.observations || canManage) && (
        <Section title="Notes">
          {canManage ? (
            <EditableCell
              value={invoice.observations ?? ''}
              placeholder="add notes"
              onSave={(v) => save('observations', v)}
              inputClass="h-7 w-full text-sm px-1"
            />
          ) : (
            <span className="text-sm">{invoice.observations}</span>
          )}
        </Section>
      )}

      {invoice.postpone_count > 0 && postponements && postponements.length > 0 && (
        <Section title={`Postponement history (${invoice.postpone_count})`}>
          <PostponementTimeline
            postponements={postponements}
            invoice={invoice}
            onMutated={invalidate}
            canManage={canManage}
          />
        </Section>
      )}
    </div>
  );
}

export default function InvoiceDetailContent({
  invoice,
  projectId,
  currency,
  projectName,
  onClose,
  onCreated,
  onDeleted,
}: InvoiceDetailContentProps): JSX.Element {
  if (!invoice) {
    return (
      <CreateForm
        projectId={projectId}
        projectName={projectName}
        currency={currency}
        onCreated={onCreated}
        onClose={onClose}
      />
    );
  }
  return (
    <EditView
      invoice={invoice}
      currency={currency}
      projectName={projectName}
      onDeleted={onDeleted}
    />
  );
}
