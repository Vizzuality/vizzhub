import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SegmentedControl } from '@/shared/components/ui/segmented-control';

const OPTIONS = [
  { value: 'project', label: 'Project' },
  { value: 'client', label: 'Client' },
] as const;

describe('SegmentedControl', () => {
  it('marks the selected option as pressed', () => {
    render(
      <SegmentedControl ariaLabel="View by" value="project" onChange={() => {}} options={OPTIONS} />,
    );
    expect(screen.getByRole('button', { name: 'Project' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Client' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('emits the new value on click', () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl ariaLabel="View by" value="project" onChange={onChange} options={OPTIONS} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Client' }));
    expect(onChange).toHaveBeenCalledWith('client');
  });
});
