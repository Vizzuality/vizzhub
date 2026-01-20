import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Settings from '../Settings';

vi.mock('../../hooks/useScores', () => ({
  useScoringConfig: () => ({
    data: {
      targets: {},
      global_weights: {},
      constants: {},
    },
    isLoading: false,
  }),
  useConfigValidation: () => ({
    data: null,
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
  it('renders Configuration tab', () => {
    renderWithProviders(<Settings />);

    expect(screen.getByText('Configuration')).toBeInTheDocument();
  });

  it('renders Validation tab', () => {
    renderWithProviders(<Settings />);

    expect(screen.getByText('Validation')).toBeInTheDocument();
  });

  it('renders Edit Configuration button when not editing', () => {
    renderWithProviders(<Settings />);

    expect(screen.getByRole('button', { name: /edit configuration/i })).toBeInTheDocument();
  });
});
