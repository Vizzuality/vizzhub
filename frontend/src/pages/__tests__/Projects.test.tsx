import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import Projects from '../Projects';
import type { Project, PaginatedProjects } from '../../types';

const mockProjects: Project[] = [
  {
    id: 'project-1',
    name: 'Alpha Project',
    jira_project_key: 'ALPHA',
    github_repo: 'org/alpha',
    start_date: '2026-01-01',
    end_date: null,
    status: 'in_progress',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-15T00:00:00Z',
  },
  {
    id: 'project-2',
    name: 'Beta Project',
    jira_project_key: 'BETA',
    github_repo: 'org/beta',
    start_date: '2025-06-01',
    end_date: '2025-12-31',
    status: 'finished',
    created_at: '2025-06-01T00:00:00Z',
    updated_at: '2025-12-31T00:00:00Z',
  },
];

const mockPaginatedResponse: PaginatedProjects = {
  items: mockProjects,
  total: 2,
  page: 1,
  page_size: 45,
  pages: 1,
};

const mockUsePaginatedProjects = vi.fn(() => ({
  data: mockPaginatedResponse,
  isLoading: false,
  error: null,
}));

const mockCreateProject = vi.fn(() => ({
  mutateAsync: vi.fn(),
  isPending: false,
}));

vi.mock('../../hooks/useProjects', () => ({
  usePaginatedProjects: (...args: unknown[]) => mockUsePaginatedProjects(...args),
  useCreateProject: () => mockCreateProject(),
}));

vi.mock('../../services/api', () => ({
  scoresApi: {
    getProjectScores: vi.fn(() => Promise.resolve({ scores: { score: 85 } })),
    getBatchScores: vi.fn(() => Promise.resolve({ scores: {}, errors: {} })),
  },
  slackApi: {
    getStatus: vi.fn(() => Promise.resolve({ configured: false })),
    getChannels: vi.fn(() => Promise.resolve([])),
  },
}));

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

function renderWithProviders(ui: React.ReactElement): ReturnType<typeof render> {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Projects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockUsePaginatedProjects.mockReturnValue({
      data: mockPaginatedResponse,
      isLoading: false,
      error: null,
    });
    mockCreateProject.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });
  });

  describe('Page Rendering', () => {
    it('renders Projects heading', () => {
      renderWithProviders(<Projects />);

      expect(screen.getByText('Projects')).toBeInTheDocument();
    });

    it('renders project cards when data loaded', () => {
      renderWithProviders(<Projects />);

      expect(screen.getByText('Alpha Project')).toBeInTheDocument();
      expect(screen.getByText('Beta Project')).toBeInTheDocument();
    });

    it('renders Create Project button', () => {
      renderWithProviders(<Projects />);

      expect(screen.getByRole('button', { name: /create project/i })).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading spinner while fetching', () => {
      mockUsePaginatedProjects.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      renderWithProviders(<Projects />);

      expect(document.querySelector('.animate-spin')).toBeTruthy();
    });
  });

  describe('Error State', () => {
    it('displays error message when loading fails', () => {
      mockUsePaginatedProjects.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to fetch projects'),
      });

      renderWithProviders(<Projects />);

      expect(screen.getByText(/error loading projects/i)).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays empty state when no projects', () => {
      mockUsePaginatedProjects.mockReturnValue({
        data: { items: [], total: 0, page: 1, page_size: 45, pages: 1 },
        isLoading: false,
        error: null,
      });

      renderWithProviders(<Projects />);

      expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create your first project/i })).toBeInTheDocument();
    });
  });

  describe('Sort Controls', () => {
    it('renders sort buttons', () => {
      renderWithProviders(<Projects />);

      expect(screen.getByRole('button', { name: /name/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /created/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /status/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /score/i })).toBeInTheDocument();
    });

    it('sort buttons can be clicked', () => {
      renderWithProviders(<Projects />);

      const nameButton = screen.getByRole('button', { name: /name/i });
      fireEvent.click(nameButton);

      expect(screen.getByRole('button', { name: /name/i })).toBeInTheDocument();
    });
  });

  describe('View Mode Toggle', () => {
    it('toggles between list and grid view', () => {
      renderWithProviders(<Projects />);

      const listButton = screen.getByTitle('List view');
      const gridButton = screen.getByTitle('Grid view');

      expect(listButton).toBeInTheDocument();
      expect(gridButton).toBeInTheDocument();

      fireEvent.click(gridButton);
      expect(localStorage.getItem('projectsViewMode')).toBe('grid');
    });

    it('persists view mode to localStorage', () => {
      renderWithProviders(<Projects />);

      const gridButton = screen.getByTitle('Grid view');
      fireEvent.click(gridButton);

      expect(localStorage.getItem('projectsViewMode')).toBe('grid');
    });
  });

  describe('Create Form', () => {
    it('shows create form when clicking Create Project button', () => {
      renderWithProviders(<Projects />);

      const createButton = screen.getByRole('button', { name: /create project/i });
      fireEvent.click(createButton);

      expect(screen.getByText(/create new project/i)).toBeInTheDocument();
    });
  });

  describe('Pagination', () => {
    it('shows pagination info when projects exist', () => {
      renderWithProviders(<Projects />);

      expect(screen.getByText(/showing 2 of 2 projects/i)).toBeInTheDocument();
      expect(screen.getByText(/page 1 of 1/i)).toBeInTheDocument();
    });

    it('renders previous and next buttons', () => {
      mockUsePaginatedProjects.mockReturnValue({
        data: {
          items: mockProjects,
          total: 50,
          page: 2,
          page_size: 45,
          pages: 2,
        },
        isLoading: false,
        error: null,
      });

      renderWithProviders(<Projects />);

      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    it('disables previous button on first page', () => {
      renderWithProviders(<Projects />);

      const prevButton = screen.getByRole('button', { name: /previous/i });
      expect(prevButton).toBeDisabled();
    });

    it('disables next button on last page', () => {
      renderWithProviders(<Projects />);

      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });
  });

  describe('Search', () => {
    it('renders search input', () => {
      renderWithProviders(<Projects />);

      expect(screen.getByPlaceholderText(/search by name/i)).toBeInTheDocument();
    });
  });
});
