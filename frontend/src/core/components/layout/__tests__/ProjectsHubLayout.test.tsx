import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import ProjectsHubLayout from '../ProjectsHubLayout';

describe('ProjectsHubLayout', () => {
  it('renders the hub tabs above the routed page', () => {
    render(
      <MemoryRouter initialEntries={['/projects']}>
        <Routes>
          <Route element={<ProjectsHubLayout />}>
            <Route path="/projects" element={<div>page-content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Tracker' })).toBeInTheDocument();
    expect(screen.getByText('page-content')).toBeInTheDocument();
  });
});
