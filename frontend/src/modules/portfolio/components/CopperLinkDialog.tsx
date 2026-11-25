import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { useLinkClientsWithCopper, useUpdateClient } from '../hooks/useClients';
import type {
  CopperCompanyCandidate,
  CopperLinkReason,
  CopperLinkReport,
  CopperLinkReviewItem,
} from '../types/portfolio';

interface CopperLinkDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

const REASON_TEXT: Record<CopperLinkReason, string> = {
  ambiguous_in_copper: 'Several Copper companies share this name. Pick the right one.',
  duplicate_in_vizzhub:
    'Another client with this name is already linked. Merge this duplicate into it.',
  not_in_copper: 'No Copper company with this name.',
};

function candidateLabel(c: CopperCompanyCandidate): string {
  const parts = [
    c.email_domain ?? 'no domain',
    c.created_on ? `created ${c.created_on}` : null,
    `${c.interaction_count} interactions`,
  ].filter(Boolean);
  return `${c.name} · ${parts.join(' · ')}`;
}

function runButtonLabel(isPending: boolean, hasReport: boolean): string {
  if (isPending) return 'Linking...';
  return hasReport ? 'Run again' : 'Link now';
}

interface ReviewRowProps {
  readonly item: CopperLinkReviewItem;
  readonly onLinked: (clientId: string) => void;
}

function ReviewRow({ item, onLinked }: ReviewRowProps): JSX.Element {
  const update = useUpdateClient();
  const [choice, setChoice] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canLink = item.reason === 'ambiguous_in_copper';

  const handleLink = async (): Promise<void> => {
    if (choice === null) return;
    setError(null);
    try {
      await update.mutateAsync({ id: item.client_id, data: { copper_company_id: choice } });
      onLinked(item.client_id);
    } catch {
      setError('That Copper company is already linked to another client.');
    }
  };

  return (
    <li className="space-y-2 border-b border-border py-3 last:border-b-0">
      <p className="text-sm font-medium text-foreground">{item.client_name}</p>
      <p className="text-xs text-muted-foreground">{REASON_TEXT[item.reason]}</p>
      {canLink && (
        <div className="space-y-1">
          {item.candidates.map((c) => (
            <label key={c.id} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`copper-${item.client_id}`}
                checked={choice === c.id}
                onChange={() => setChoice(c.id)}
              />
              <span className="font-mono text-xs">{candidateLabel(c)}</span>
            </label>
          ))}
          <Button size="sm" onClick={handleLink} disabled={choice === null || update.isPending}>
            Link
          </Button>
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      )}
    </li>
  );
}

export function CopperLinkDialog({ open, onOpenChange }: CopperLinkDialogProps): JSX.Element {
  const link = useLinkClientsWithCopper();
  const [report, setReport] = useState<CopperLinkReport | null>(null);

  const handleRun = async (): Promise<void> => {
    try {
      setReport(await link.mutateAsync());
    } catch {
      // Rendered from link.isError; swallowing avoids an unhandled rejection.
    }
  };

  const handleLinked = (clientId: string): void => {
    setReport((r) => r && { ...r, review: r.review.filter((i) => i.client_id !== clientId) });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Link clients with Copper</DialogTitle>
          <DialogDescription>
            Links each client to the Copper company with exactly the same name. Nothing is
            renamed or merged; unclear cases are listed for review.
          </DialogDescription>
        </DialogHeader>

        {report ? (
          <div className="space-y-3">
            <p className="text-sm text-foreground">
              <span className="font-mono tabular-nums">{report.linked}</span> clients linked now,{' '}
              <span className="font-mono tabular-nums">{report.already_linked}</span> were
              already linked.{' '}
              {report.review.length > 0
                ? `${report.review.length} need review:`
                : 'Nothing left to review.'}
            </p>
            {report.review.length > 0 && (
              <ul className="max-h-[50vh] overflow-y-auto pr-2">
                {report.review.map((item) => (
                  <ReviewRow key={item.client_id} item={item} onLinked={handleLinked} />
                ))}
              </ul>
            )}
          </div>
        ) : (
          link.isError && (
            <p className="text-sm text-destructive">
              Could not read Copper. Check the Copper integration in Admin → Integrations.
            </p>
          )
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button onClick={handleRun} disabled={link.isPending}>
            {runButtonLabel(link.isPending, report !== null)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
