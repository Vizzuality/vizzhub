import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Settings from '../Settings';

vi.mock('../../hooks/useConfig', () => ({
  useConfigParameters: () => ({
    data: {
      'Targets': [],
      'Global Weights': [],
    },
    isLoading: false,
    error: null,
  }),
  useUpdateConfigParameters: () => ({
    mutateAsync: vi.fn(),
  }),
}));

vi.mock('../../hooks/useConfigEditor', () => ({
  useConfigEditor: () => ({
    editedValues: new Map(),
    updateValue: vi.fn(),
    validationErrors: [],
    canSave: false,
    getUpdates: vi.fn(() => []),
    reset: vi.fn(),
  }),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('Settings', () => {
  it('renders Settings heading', () => {
    renderWithProviders(<Settings />);

    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders Edit Configuration button when not editing', () => {
    renderWithProviders(<Settings />);

    expect(screen.getByRole('button', { name: /edit configuration/i })).toBeInTheDocument();
  });
});
