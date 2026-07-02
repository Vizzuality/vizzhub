import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import {
  createMemoryRouter,
  RouterProvider,
  Navigate,
  useLocation,
  useParams,
} from 'react-router-dom';
import ProjectHubLayout from '../ProjectHub';
import { useUrlState } from '@/shared/hooks/useUrlState';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/core/hooks/useProjects', () => ({
  useProject: () => ({
    data: { id: 'p1', name: 'X', has_scorecard: true, status: 'live' },
    isLoading: false,
  }),
}));

vi.mock('@/core/permissions', () => ({
  usePermission: () => true,
  Action: {
    PROJECTS_MANAGE: 'projects:manage',
    SCORECARD_VIEW: 'scorecard:view',
    TRACKER_VIEW: 'tracker:view',
    PORTFOLIO_VIEW: 'portfolio:view',
  },
}));

// ---------------------------------------------------------------------------
// Lightweight fake facet panels
// ---------------------------------------------------------------------------

function FakeTrackerPanel(): JSX.Element {
  const { state } = useUrlState({ period: { defaultValue: '' } });
  return (
    <div>
      <span data-testid="tracker-panel">TRACKER PANEL</span>
      <span data-testid="period-value">{state.period}</span>
    </div>
  );
}

function FakeScorecardPanel(): JSX.Element {
  return <div data-testid="scorecard-panel">SCORECARD PANEL</div>;
}

function FakeOverviewPanel(): JSX.Element {
  return <div data-testid="overview-panel">OVERVIEW PANEL</div>;
}

// Reads the current location so each assertion can inspect pathname + search.
function LocationProbe(): JSX.Element {
  const { pathname, search } = useLocation();
  return <span data-testid="loc">{pathname}{search}</span>;
}

// Legacy redirect — mirrors LegacyTrackerRedirect in App.tsx.
function LegacyTrackerRedirect(): JSX.Element {
  const { projectId } = useParams<{ projectId: string }>();
  const { search } = useLocation();
  return <Navigate to={`/projects/${projectId}/tracker${search}`} replace />;
}

// ---------------------------------------------------------------------------
// Route config factory
// ---------------------------------------------------------------------------

function buildRoutes() {
  return [
    // Hub route with fake facet panels as children.
    {
      path: '/projects/:id',
      element: (
        <>
          <ProjectHubLayout />
          <LocationProbe />
        </>
      ),
      children: [
        { index: true, element: <Navigate to="overview" replace /> },
        { path: 'overview', element: <FakeOverviewPanel /> },
        { path: 'scorecard', element: <FakeScorecardPanel /> },
        { path: 'tracker', element: <FakeTrackerPanel /> },
      ],
    },
    // Legacy redirect route.
    {
      path: '/tracker/projects/:projectId',
      element: (
        <>
          <LegacyTrackerRedirect />
          <LocationProbe />
        </>
      ),
    },
  ];
}

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProjectHub history & filter preservation', () => {
  it('scenario 1: deep-link with ?period=2026-05 renders the filter value', () => {
    const router = createMemoryRouter(buildRoutes(), {
      initialEntries: ['/projects/p1/tracker?period=2026-05'],
      initialIndex: 0,
    });

    render(<RouterProvider router={router} />);

    // The tracker panel must be visible.
    expect(screen.getByTestId('tracker-panel')).toBeInTheDocument();

    // The period param must be read from the URL via useUrlState.
    expect(screen.getByTestId('period-value').textContent).toBe('2026-05');

    // Location probe confirms full URL.
    expect(screen.getByTestId('loc').textContent).toBe('/projects/p1/tracker?period=2026-05');
  });

  it('scenario 2: tab-switch to Scorecard strips filter; Back restores it', async () => {
    const router = createMemoryRouter(buildRoutes(), {
      initialEntries: ['/projects/p1/tracker?period=2026-05'],
      initialIndex: 0,
    });

    render(<RouterProvider router={router} />);

    // Confirm we start on tracker with the filter.
    expect(screen.getByTestId('loc').textContent).toBe('/projects/p1/tracker?period=2026-05');

    // Click the Scorecard tab link — it must navigate to the clean base path
    // /projects/p1/scorecard with NO query params (cross-facet isolation).
    const scorecardTab = screen.getByRole('link', { name: /scorecard/i });
    fireEvent.click(scorecardTab);

    expect(screen.getByTestId('loc').textContent).toBe('/projects/p1/scorecard');
    expect(screen.getByTestId('scorecard-panel')).toBeInTheDocument();

    // Simulate browser Back via router.navigate(-1).
    await act(async () => {
      await router.navigate(-1);
    });

    // After Back, the full original URL — including ?period=2026-05 — must be
    // restored. The browser history entry still holds the search string.
    expect(screen.getByTestId('loc').textContent).toBe('/projects/p1/tracker?period=2026-05');
    expect(screen.getByTestId('period-value').textContent).toBe('2026-05');
  });

  it('scenario 3: legacy /tracker/projects/:id?period= redirects with search preserved', () => {
    const router = createMemoryRouter(buildRoutes(), {
      initialEntries: ['/tracker/projects/p1?period=2026-05'],
      initialIndex: 0,
    });

    render(<RouterProvider router={router} />);

    // After the replace-redirect the URL must be the hub tracker path with
    // the original query string intact.
    expect(screen.getByTestId('loc').textContent).toBe('/projects/p1/tracker?period=2026-05');
  });
});
