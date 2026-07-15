import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, describe, expect, it } from 'vitest';
import { AppSidebar } from '../AppSidebar';
import { SidebarProvider } from '@/shared/components/ui/sidebar';

beforeAll(() => {
  // jsdom lacks matchMedia; SidebarProvider's mobile detection needs it.
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
});

function renderAt(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </MemoryRouter>,
  );
}

describe('AppSidebar active state', () => {
  // Regression: GuardedLink must forward Slot-injected props (data-active,
  // data-sidebar) to the anchor — without it leaf links never mark active.
  it('marks the current leaf link as active', () => {
    renderAt('/tracker/my-report');
    expect(screen.getByRole('link', { name: 'My Report' })).toHaveAttribute(
      'data-active',
      'true',
    );
  });

  it('leaves other leaf links inactive', () => {
    renderAt('/tracker/my-report');
    expect(screen.getByRole('link', { name: 'Playbook' })).toHaveAttribute(
      'data-active',
      'false',
    );
  });
});
