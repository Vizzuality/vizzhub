import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { RedirectWithSearch } from '../RedirectWithSearch';

function LocationProbe(): JSX.Element {
  const { search } = useLocation();
  return <span data-testid="search">{search}</span>;
}

describe('RedirectWithSearch', () => {
  it('preserves the query string on redirect', () => {
    render(
      <MemoryRouter initialEntries={['/old?period=2026-05']}>
        <Routes>
          <Route path="/old" element={<RedirectWithSearch to="/new" />} />
          <Route path="/new" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('search').textContent).toBe('?period=2026-05');
  });

  it('redirects without query string when none is present', () => {
    render(
      <MemoryRouter initialEntries={['/old']}>
        <Routes>
          <Route path="/old" element={<RedirectWithSearch to="/new" />} />
          <Route path="/new" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('search').textContent).toBe('');
  });
});
