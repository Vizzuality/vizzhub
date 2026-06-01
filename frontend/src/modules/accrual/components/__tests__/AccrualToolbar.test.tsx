import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AccrualToolbar } from '@/modules/accrual/components/AccrualToolbar';

const defaultFilters = { year_from: 2026, year_to: 2026, issues_only: false, search: '' };

describe('AccrualToolbar', () => {
  it('renders the current year range', () => {
    render(<AccrualToolbar filters={defaultFilters} onChange={vi.fn()} />);
    expect(screen.getByText('2026')).toBeInTheDocument();
  });

  it('next-year arrow shifts both year_from and year_to forward', async () => {
    const onChange = vi.fn();
    render(<AccrualToolbar filters={defaultFilters} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: /next year/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ year_from: 2027, year_to: 2027 }),
    );
  });

  it('previous-year arrow shifts both year_from and year_to back', async () => {
    const onChange = vi.fn();
    render(<AccrualToolbar filters={defaultFilters} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: /previous year/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ year_from: 2025, year_to: 2025 }),
    );
  });

  it('shifting preserves the range size for multi-year views', async () => {
    const onChange = vi.fn();
    render(
      <AccrualToolbar
        filters={{ year_from: 2024, year_to: 2026, issues_only: false }}
        onChange={onChange}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /next year/i }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ year_from: 2025, year_to: 2027 }),
    );
  });

  it('disables the previous-year arrow at the lower bound', () => {
    render(
      <AccrualToolbar
        filters={{ ...defaultFilters, year_from: 2024 }}
        onChange={vi.fn()}
        minYear={2024}
        maxYear={2030}
      />,
    );
    expect(screen.getByRole('button', { name: /previous year/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next year/i })).not.toBeDisabled();
  });

  it('disables the next-year arrow at the upper bound', () => {
    render(
      <AccrualToolbar
        filters={{ ...defaultFilters, year_to: 2030 }}
        onChange={vi.fn()}
        minYear={2024}
        maxYear={2030}
      />,
    );
    expect(screen.getByRole('button', { name: /next year/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /previous year/i })).not.toBeDisabled();
  });

  it('leaves both arrows enabled when bounds are unset', () => {
    render(<AccrualToolbar filters={defaultFilters} onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: /previous year/i })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: /next year/i })).not.toBeDisabled();
  });

  it('emits the typed query through onChange.search', async () => {
    const onChange = vi.fn();
    render(<AccrualToolbar filters={defaultFilters} onChange={onChange} />);
    await userEvent.type(
      screen.getByRole('searchbox', { name: /filter by project/i }),
      'a',
    );
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ search: 'a' }));
  });

  it('shows a clear button that resets the search when a query is present', async () => {
    const onChange = vi.fn();
    render(
      <AccrualToolbar filters={{ ...defaultFilters, search: 'foo' }} onChange={onChange} />,
    );
    await userEvent.click(screen.getByRole('button', { name: /clear filter/i }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ search: '' }));
  });

  it('toggles a column via the Columns dropdown', async () => {
    const onToggleColumn = vi.fn();
    render(
      <AccrualToolbar
        filters={defaultFilters}
        onChange={vi.fn()}
        hiddenColumns={new Set()}
        onToggleColumn={onToggleColumn}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /columns/i }));
    await userEvent.click(await screen.findByRole('menuitemcheckbox', { name: 'Projects' }));
    expect(onToggleColumn).toHaveBeenCalledWith('projects');
  });

  it('calls onToggleCollapsed when the Collapse button is clicked', async () => {
    const onToggleCollapsed = vi.fn();
    render(
      <AccrualToolbar
        filters={defaultFilters}
        onChange={vi.fn()}
        onToggleCollapsed={onToggleCollapsed}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /collapse fixed columns/i }));
    expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
  });

  it('labels the button Expand and disables Columns while collapsed', () => {
    render(
      <AccrualToolbar
        filters={defaultFilters}
        onChange={vi.fn()}
        collapsed
        onToggleCollapsed={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /expand fixed columns/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Columns' })).toBeDisabled();
  });

  it('omits the collapse button when no handler is provided', () => {
    render(<AccrualToolbar filters={defaultFilters} onChange={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /collapse fixed columns/i })).toBeNull();
  });
});
