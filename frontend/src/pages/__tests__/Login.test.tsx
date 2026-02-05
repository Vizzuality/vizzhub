import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Login from '../Login';

const mockUseAuth = vi.fn(() => ({
  isLoading: false,
  isAuthenticated: false,
  user: null,
  login: vi.fn(),
  logout: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function renderWithProviders(ui: React.ReactElement): ReturnType<typeof render> {
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isLoading: false,
      isAuthenticated: false,
      user: null,
      login: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });
  });

  describe('Page Rendering', () => {
    it('renders Project Scorecard heading', () => {
      renderWithProviders(<Login />);

      expect(screen.getByText('Project Scorecard')).toBeInTheDocument();
    });

    it('renders sign in description', () => {
      renderWithProviders(<Login />);

      expect(screen.getByText(/sign in with your company google account/i)).toBeInTheDocument();
    });

    it('renders Google sign in button', () => {
      renderWithProviders(<Login />);

      expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument();
    });

    it('renders restricted access notice', () => {
      renderWithProviders(<Login />);

      expect(screen.getByText(/restricted to authorized company domain users/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading state when auth is loading', () => {
      mockUseAuth.mockReturnValue({
        isLoading: true,
        isAuthenticated: false,
        user: null,
        login: vi.fn(),
        logout: vi.fn().mockResolvedValue(undefined),
      });

      renderWithProviders(<Login />);

      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  describe('Google Sign In Button', () => {
    it('shows alert when Google sign in is clicked', () => {
      const alertSpy = vi.spyOn(globalThis, 'alert').mockImplementation(() => {});

      renderWithProviders(<Login />);

      const googleButton = screen.getByRole('button', { name: /sign in with google/i });
      fireEvent.click(googleButton);

      expect(alertSpy).toHaveBeenCalled();

      alertSpy.mockRestore();
    });
  });

  describe('Accessibility', () => {
    it('renders SVG icon in sign in button', () => {
      renderWithProviders(<Login />);

      const button = screen.getByRole('button', { name: /sign in with google/i });
      const svg = button.querySelector('svg');

      expect(svg).toBeTruthy();
    });
  });
});
