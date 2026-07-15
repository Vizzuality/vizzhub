import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from '../StatusBadge';

// Status display convention: colored dot + plain text, never tinted pills.
describe('StatusBadge', () => {
  it.each([
    ['live', 'Live', 'bg-score-green'],
    ['proposal', 'Proposal', 'bg-score-yellow'],
    ['finished', 'Finished', 'bg-muted-foreground'],
  ])('renders %s as a %s label with a colored dot', (status, label, dotClass) => {
    const { container } = render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelector(`span.${dotClass}`)).not.toBeNull();
  });

  it('falls back to a neutral dot and the raw status for unknown values', () => {
    const { container } = render(<StatusBadge status="archived" />);
    expect(screen.getByText('archived')).toBeInTheDocument();
    expect(container.querySelector('span.bg-muted-foreground')).not.toBeNull();
  });
});
