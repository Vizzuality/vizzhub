import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PlannerAddRow } from '@/modules/capacity/components/PlannerAddRow';

describe('PlannerAddRow', () => {
  const options = [
    { id: '3', name: 'Zebra' },
    { id: '1', name: 'Apple' },
    { id: '2', name: 'mango' },
    { id: '4', name: 'Banana' },
  ];

  it('renders options sorted alphabetically (case-insensitive)', async () => {
    render(
      <PlannerAddRow
        options={options}
        existingIds={new Set()}
        onSelect={() => {}}
        label="Add project"
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /add project/i }));
    const items = screen.getAllByRole('option').map((el) => el.textContent);
    expect(items).toEqual(['Apple', 'Banana', 'mango', 'Zebra']);
  });

  it('filters out existing ids before sorting', async () => {
    render(
      <PlannerAddRow
        options={options}
        existingIds={new Set(['1', '3'])}
        onSelect={() => {}}
        label="Add project"
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: /add project/i }));
    const items = screen.getAllByRole('option').map((el) => el.textContent);
    expect(items).toEqual(['Banana', 'mango']);
  });
});
