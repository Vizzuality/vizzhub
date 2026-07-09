import { ExternalLink } from 'lucide-react';
import { PROFILE_TEXT_FIELDS } from '../utils/programs';
import type { ProgramProfile } from '../types/portfolio';

function FieldValue({
  fieldKey,
  value,
}: {
  readonly fieldKey: string;
  readonly value: string;
}): JSX.Element {
  if (!value) return <span className="text-sm text-muted-foreground/50">—</span>;
  // Only link http(s) — anything else (javascript:, data:, …) renders as plain text.
  if (fieldKey === 'website_url' && /^https?:\/\//i.test(value)) {
    return (
      <a
        href={value}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-sm text-primary underline-offset-2 hover:underline"
      >
        <span className="truncate">{value}</span>
        <ExternalLink className="h-3.5 w-3.5 shrink-0" />
      </a>
    );
  }
  return <p className="whitespace-pre-wrap text-sm leading-relaxed">{value}</p>;
}

/** Read-only narrative fields; editing lives in ProgramEditForm. */
export function ProgramNarrative({
  profile,
}: {
  readonly profile: ProgramProfile | null;
}): JSX.Element {
  return (
    <section className="space-y-4">
      <h2 className="text-base font-semibold">Narrative</h2>
      <div className="grid grid-cols-1 gap-x-10 gap-y-5 md:grid-cols-2">
        {PROFILE_TEXT_FIELDS.map((f) => (
          <div key={f.key} className="space-y-1">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">{f.label}</p>
            <FieldValue fieldKey={f.key} value={profile?.[f.key] ?? ''} />
          </div>
        ))}
      </div>
    </section>
  );
}
