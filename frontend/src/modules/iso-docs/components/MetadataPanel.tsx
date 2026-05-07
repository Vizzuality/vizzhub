import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Pencil } from 'lucide-react';
import { DocViewer } from '@/shared/components/doc/DocViewer';
import { CLASSIFICATION_LABELS, STATUS_LABELS } from '../types/isoDocs';
import type { IsoDocMetadata } from '../types/isoDocs';

interface MetadataPanelProps {
  readonly metadata: IsoDocMetadata;
  readonly onEdit?: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  approved: 'bg-green-500',
  draft: 'bg-yellow-500',
  under_review: 'bg-blue-500',
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function Separator(): JSX.Element {
  return <span className="text-border">|</span>;
}

export function MetadataPanel({ metadata, onEdit }: MetadataPanelProps): JSX.Element {
  const [changelogOpen, setChangelogOpen] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);
  const hasInstructions = Boolean(metadata.instructions?.trim());

  const documentDate = useMemo(() => {
    const validEntries = (metadata.changelog ?? [])
      .filter((c) => !Number.isNaN(new Date(c.date).getTime()));
    if (validEntries.length) {
      const [latest] = [...validEntries].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
      );
      return formatDate(latest.date);
    }
    if (metadata.document_date) return formatDate(metadata.document_date);
    return formatDate(metadata.created_at);
  }, [metadata.changelog, metadata.document_date, metadata.created_at]);

  return (
    <div className="px-3 py-2.5 text-xs space-y-1.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {metadata.code && (
          <span className="font-mono font-semibold text-foreground">{metadata.code}</span>
        )}
        {metadata.standard?.map((s) => (
          <span key={s} className="font-mono text-muted-foreground">{s}</span>
        ))}
        {(metadata.code || metadata.standard?.length) && <Separator />}
        {metadata.status && (
          <span className="flex items-center gap-1">
            <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_COLORS[metadata.status] ?? 'bg-gray-400'}`} />
            <span>{STATUS_LABELS[metadata.status] ?? metadata.status}</span>
          </span>
        )}
        {metadata.doc_version && (
          <span className="text-muted-foreground font-mono">v{metadata.doc_version}</span>
        )}
        {metadata.category && (
          <>
            <Separator />
            <span className="capitalize">{metadata.category}</span>
          </>
        )}
        {documentDate && (
          <>
            <Separator />
            <span className="text-muted-foreground">{documentDate}</span>
          </>
        )}
        <Separator />
        <span className="text-muted-foreground italic">
          {CLASSIFICATION_LABELS[metadata.classification] ?? 'Internal use'}
        </span>
        {onEdit && (
          <>
            <Separator />
            <button
              className="flex items-center gap-0.5 text-muted-foreground hover:text-foreground"
              onClick={onEdit}
            >
              <Pencil className="h-3 w-3" />
            </button>
          </>
        )}
      </div>

      {!!metadata.clauses?.length && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-muted-foreground">Clauses:</span>
          <span className="font-mono text-muted-foreground">
            {metadata.clauses.join(', ')}
          </span>
        </div>
      )}

      <div className="flex items-center gap-x-2 text-muted-foreground">
        <span>Prepared: <span className="text-foreground">ISMS Manager</span></span>
        <Separator />
        <span>Reviewed: <span className="text-foreground">ISMS Manager</span></span>
        <Separator />
        <span>Approved: <span className="text-foreground">Top Management</span></span>
        {metadata.changelog && metadata.changelog.length > 0 && (
          <>
            <Separator />
            <button
              className="flex items-center gap-0.5 hover:text-foreground"
              onClick={() => setChangelogOpen(!changelogOpen)}
            >
              {changelogOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              {metadata.changelog.length} revision{metadata.changelog.length > 1 ? 's' : ''}
            </button>
          </>
        )}
        {hasInstructions && (
          <>
            <Separator />
            <button
              className="flex items-center gap-0.5 hover:text-foreground"
              onClick={() => setInstructionsOpen(!instructionsOpen)}
            >
              {instructionsOpen ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              Instructions
            </button>
          </>
        )}
      </div>

      {instructionsOpen && hasInstructions && (
        <div className="pt-1 border-t">
          <DocViewer content={metadata.instructions ?? ''} />
        </div>
      )}

      {changelogOpen && metadata.changelog && (
        <div className="pt-1 border-t space-y-0.5">
          {metadata.changelog.map((entry) => (
            <div key={`${entry.version}-${entry.date}`} className="text-muted-foreground">
              <span className="font-mono">v{entry.version}</span>
              {' — '}{entry.date}{' — '}{entry.description}
              {' '}<span className="opacity-60">({entry.author})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
