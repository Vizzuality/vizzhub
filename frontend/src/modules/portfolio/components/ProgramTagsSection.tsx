import { TermChips } from './TermChips';
import type { ProgramSummary } from '../types/portfolio';

export function ProgramTagsSection({
  program,
  canManage: _canManage,
}: {
  readonly program: ProgramSummary;
  readonly canManage: boolean;
}): JSX.Element {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium">Tags</h2>
      <TermChips terms={program.terms} />
    </section>
  );
}
