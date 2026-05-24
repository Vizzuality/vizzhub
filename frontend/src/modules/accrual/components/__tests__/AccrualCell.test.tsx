import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AccrualCell } from '@/modules/accrual/components/AccrualCell';

describe('AccrualCell', () => {
  it('shows the formatted amount', () => {
    render(
      <AccrualCell
        amount="12345.67" eurAmount="11000"
        isOverride={false} isFrozen={false} canEdit
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText('12,345.67')).toBeInTheDocument();
  });

  it('shows pin when override', () => {
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride isFrozen={false} canEdit
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('cell-override-pin')).toBeInTheDocument();
  });

  it('shows lock and is read-only when frozen', async () => {
    const onChange = vi.fn();
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen canEdit
        onChange={onChange}
      />,
    );
    expect(screen.getByTestId('cell-frozen-lock')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button'));
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('does not render edit affordance when canEdit is false', async () => {
    const onChange = vi.fn();
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit={false}
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button'));
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Enter commits and calls onChange', async () => {
    const onChange = vi.fn();
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button'));
    const input = screen.getByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, '250');
    await userEvent.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('250');
  });

  it('Escape cancels and does not call onChange', async () => {
    const onChange = vi.fn();
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button'));
    await userEvent.type(screen.getByRole('textbox'), '999');
    await userEvent.keyboard('{Escape}');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Tab commits like Enter', async () => {
    const onChange = vi.fn();
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button'));
    const input = screen.getByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, '500');
    await userEvent.tab();
    expect(onChange).toHaveBeenCalledWith('500');
  });

  it('does not call onChange when the value is unchanged', async () => {
    const onChange = vi.fn();
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button'));
    await userEvent.keyboard('{Enter}');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('renders the destructive ring when onError is true', () => {
    const { container } = render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={vi.fn()} onError
      />,
    );
    const node = container.querySelector('[class*="ring-destructive"]');
    expect(node).not.toBeNull();
  });

  it('defaults source to excel when prop omitted', () => {
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={vi.fn()}
      />,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('data-source')).toBe('excel');
    expect(btn.getAttribute('title')).toContain('From Excel');
    // Excel cells have no inline stripe background.
    expect(btn.getAttribute('style')).toBeNull();
  });

  it('renders hatched stripes for team_budget source', () => {
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride={false} isFrozen={false} canEdit
        onChange={vi.fn()} source="team_budget"
      />,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('data-source')).toBe('team_budget');
    // Inline style applies the repeating-linear-gradient stripes.
    expect(btn.getAttribute('style')).toContain('repeating-linear-gradient');
    expect(btn.getAttribute('title')).toContain('Team-budget fallback');
  });

  it('exposes manual source in the title and data-source attribute', () => {
    render(
      <AccrualCell
        amount="100" eurAmount="91"
        isOverride isFrozen={false} canEdit
        onChange={vi.fn()} source="manual"
      />,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('data-source')).toBe('manual');
    expect(btn.getAttribute('title')).toContain('Manual override');
  });
});
