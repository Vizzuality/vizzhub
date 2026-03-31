import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { IsoDocMetadata } from '../types/isoDocs';

interface MetadataPanelProps {
  readonly metadata: IsoDocMetadata;
}

const STATUS_COLORS: Record<string, string> = {
  approved: 'bg-green-500',
  draft: 'bg-yellow-500',
  under_review: 'bg-blue-500',
};

const STATUS_LABELS: Record<string, string> = {
  approved: 'Approved',
  draft: 'Draft',
  under_review: 'Under Review',
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function Separator(): JSX.Element {
  return <span className="text-border">|</span>;
}

export function MetadataPanel({ metadata }: MetadataPanelProps): JSX.Element {
  const [changelogOpen, setChangelogOpen] = useState(false);

  const documentDate = useMemo(() => {
    if (!metadata.changelog?.length) return null;
    return formatDate(metadata.changelog[0].date);
  }, [metadata.changelog]);

  return (
    <div className="border rounded px-3 py-2.5 text-xs space-y-1.5 bg-muted/30">
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
        <span className="text-muted-foreground italic">Internal use</span>
      </div>

      {metadata.clauses && metadata.clauses.length > 0 && (
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
      </div>

      {changelogOpen && metadata.changelog && (
        <div className="pt-1 border-t space-y-0.5">
          {metadata.changelog.map((entry, i) => (
            <div key={i} className="text-muted-foreground">
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
