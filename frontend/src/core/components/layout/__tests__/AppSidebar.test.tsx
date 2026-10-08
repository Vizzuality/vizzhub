import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import { AppSidebar } from '../AppSidebar';
import { SidebarProvider, SidebarTrigger } from '@/shared/components/ui/sidebar';

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

describe('AppSidebar on mobile', () => {
  const desktopWidth = window.innerWidth;

  afterEach(() => {
    window.innerWidth = desktopWidth;
  });

  // Regression: the only toggle lived inside the sidebar, which on mobile is a
  // hidden sheet — the menu could never be opened.
  it('opens from an external trigger and closes after navigating', async () => {
    window.innerWidth = 500;
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarProvider>
          <SidebarTrigger />
          <AppSidebar />
        </SidebarProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByRole('link', { name: 'Playbook' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Toggle Sidebar' }));
    const link = await screen.findByRole('link', { name: 'Playbook' });

    await act(async () => {
      await user.click(link);
    });

    expect(screen.queryByRole('link', { name: 'Playbook' })).not.toBeInTheDocument();
  });
});
