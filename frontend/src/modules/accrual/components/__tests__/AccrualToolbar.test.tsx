import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AccrualToolbar } from '@/modules/accrual/components/AccrualToolbar';

const defaultFilters = { year_from: 2026, year_to: 2026, status: 'live' as const, currency: 'all' };

describe('AccrualToolbar', () => {
  it('renders the current year range', () => {
    render(<AccrualToolbar filters={defaultFilters} onChange={vi.fn()} currencies={['USD', 'GBP']} />);
    expect(screen.getByText('2026')).toBeInTheDocument();
  });

  it('next-year arrow advances year_to', async () => {
    const onChange = vi.fn();
    render(<AccrualToolbar filters={defaultFilters} onChange={onChange} currencies={['USD']} />);
    await userEvent.click(screen.getByRole('button', { name: /next year/i }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ year_to: 2027 }));
  });

  it('previous-year arrow rewinds year_from', async () => {
    const onChange = vi.fn();
    render(<AccrualToolbar filters={defaultFilters} onChange={onChange} currencies={['USD']} />);
    await userEvent.click(screen.getByRole('button', { name: /previous year/i }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ year_from: 2025 }));
  });

  it('status select changes status', async () => {
    const onChange = vi.fn();
    render(<AccrualToolbar filters={defaultFilters} onChange={onChange} currencies={['USD']} />);
    await userEvent.click(screen.getByRole('combobox', { name: /status/i }));
    await userEvent.click(screen.getByRole('option', { name: /all/i }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ status: 'all' }));
  });

  it('currency select offers each currency plus "all"', async () => {
    render(
      <AccrualToolbar
        filters={defaultFilters}
        onChange={vi.fn()}
        currencies={['USD', 'GBP', 'CAD']}
      />,
    );
    await userEvent.click(screen.getByRole('combobox', { name: /currency/i }));
    expect(screen.getByRole('option', { name: /all/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /USD/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /GBP/i })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /CAD/i })).toBeInTheDocument();
  });

  it('includes EUR in the dropdown when projects use EUR', async () => {
    render(
      <AccrualToolbar
        filters={defaultFilters}
        onChange={vi.fn()}
        currencies={['EUR', 'USD']}
      />,
    );
    await userEvent.click(screen.getByRole('combobox', { name: /currency/i }));
    expect(screen.getByRole('option', { name: /EUR/i })).toBeInTheDocument();
  });

  it('disables the previous-year arrow at the lower bound', () => {
    render(
      <AccrualToolbar
        filters={{ ...defaultFilters, year_from: 2024 }}
        onChange={vi.fn()}
        currencies={[]}
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
        currencies={[]}
        minYear={2024}
        maxYear={2030}
      />,
    );
    expect(screen.getByRole('button', { name: /next year/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /previous year/i })).not.toBeDisabled();
  });

  it('leaves both arrows enabled when bounds are unset', () => {
    render(<AccrualToolbar filters={defaultFilters} onChange={vi.fn()} currencies={[]} />);
    expect(screen.getByRole('button', { name: /previous year/i })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: /next year/i })).not.toBeDisabled();
  });
});
