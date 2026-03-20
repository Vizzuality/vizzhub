import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EVMForm from './EVMForm';

describe('EVMForm', () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all input fields', () => {
    render(<EVMForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} />);

    expect(screen.getByLabelText(/total budget/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/actual cost/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/work completed/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/expected progress/i)).toBeInTheDocument();
  });

  it('pre-fills form with initial data', () => {
    const initialData = {
      budget_total: 100000,
      cost_to_date: 45000,
      percent_completed: 0.5,
      percent_planned: 0.45,
    };

    render(
      <EVMForm
        initialData={initialData}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByLabelText(/total budget/i)).toHaveValue(100000);
    expect(screen.getByLabelText(/actual cost/i)).toHaveValue(45000);
    expect(screen.getByLabelText(/work completed/i)).toHaveValue(50);
    expect(screen.getByLabelText(/expected progress/i)).toHaveValue(45);
  });

  it('shows calculated values when data is entered', async () => {
    render(<EVMForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} />);

    const budgetInput = screen.getByLabelText(/total budget/i);
    const costInput = screen.getByLabelText(/actual cost/i);
    const completedInput = screen.getByLabelText(/work completed/i);
    const plannedInput = screen.getByLabelText(/expected progress/i);

    fireEvent.change(budgetInput, { target: { value: '100000' } });
    fireEvent.change(costInput, { target: { value: '50000' } });
    fireEvent.change(completedInput, { target: { value: '50' } });
    fireEvent.change(plannedInput, { target: { value: '40' } });

    await waitFor(() => {
      expect(screen.getByText(/50\.000/)).toBeInTheDocument();
      expect(screen.getByText('1.25')).toBeInTheDocument();
      expect(screen.getByText('1.00')).toBeInTheDocument();
    });
  });

  it('calls onCancel when cancel button is clicked', () => {
    render(<EVMForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} />);

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('shows loading state when isLoading is true', () => {
    render(
      <EVMForm
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
        isLoading={true}
      />
    );

    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();
  });

  it('shows performance labels for SPI and CPI', async () => {
    render(<EVMForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} />);

    const budgetInput = screen.getByLabelText(/total budget/i);
    const costInput = screen.getByLabelText(/actual cost/i);
    const completedInput = screen.getByLabelText(/work completed/i);
    const plannedInput = screen.getByLabelText(/expected progress/i);

    fireEvent.change(budgetInput, { target: { value: '100000' } });
    fireEvent.change(costInput, { target: { value: '60000' } });
    fireEvent.change(completedInput, { target: { value: '50' } });
    fireEvent.change(plannedInput, { target: { value: '60' } });

    await waitFor(() => {
      expect(screen.getByText(/behind schedule/i)).toBeInTheDocument();
      expect(screen.getByText(/over budget/i)).toBeInTheDocument();
    });
  });

  it('shows ahead of schedule and under budget for good performance', async () => {
    render(<EVMForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} />);

    const budgetInput = screen.getByLabelText(/total budget/i);
    const costInput = screen.getByLabelText(/actual cost/i);
    const completedInput = screen.getByLabelText(/work completed/i);
    const plannedInput = screen.getByLabelText(/expected progress/i);

    fireEvent.change(budgetInput, { target: { value: '100000' } });
    fireEvent.change(costInput, { target: { value: '40000' } });
    fireEvent.change(completedInput, { target: { value: '60' } });
    fireEvent.change(plannedInput, { target: { value: '50' } });

    await waitFor(() => {
      expect(screen.getByText(/ahead of schedule/i)).toBeInTheDocument();
      expect(screen.getByText(/under budget/i)).toBeInTheDocument();
    });
  });
});
