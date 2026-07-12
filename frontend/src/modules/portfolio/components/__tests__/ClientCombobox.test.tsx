import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ClientCombobox } from '../ClientCombobox';

vi.mock('../../hooks/useClientOptions', () => ({
  useClientOptions: () => ({
    data: [
      { id: 'c1', name: 'Acme' },
      { id: 'c2', name: 'Globex' },
    ],
  }),
}));

describe('ClientCombobox', () => {
  it('filters options by typing and selects one', () => {
    const onChange = vi.fn();
    render(<ClientCombobox value="" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /all clients/i }));
    fireEvent.change(screen.getByPlaceholderText(/search clients/i), {
      target: { value: 'glo' },
    });
    expect(screen.queryByText('Acme')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Globex'));
    expect(onChange).toHaveBeenCalledWith('c2');
  });

  it('offers an All clients option to clear the filter', () => {
    const onChange = vi.fn();
    render(<ClientCombobox value="c1" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /acme/i }));
    fireEvent.click(screen.getByText('All clients'));
    expect(onChange).toHaveBeenCalledWith('');
  });
});
