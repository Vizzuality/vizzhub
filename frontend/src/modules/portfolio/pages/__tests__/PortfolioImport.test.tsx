import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import PortfolioImport from '../PortfolioImport';

const mockPermission = vi.fn();

vi.mock('@/core/permissions/usePermission', () => ({
  usePermission: (...args: Parameters<typeof mockPermission>) => mockPermission(...args),
}));

function renderPage(): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PortfolioImport />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PortfolioImport', () => {
  it('shows the upload dropzone for a manager', () => {
    mockPermission.mockReturnValue(true);
    renderPage();
    expect(screen.getByLabelText('Overview spreadsheet')).toBeInTheDocument();
  });

  it('redirects a non-manager away (no upload control)', () => {
    mockPermission.mockReturnValue(false);
    renderPage();
    expect(screen.queryByLabelText('Overview spreadsheet')).not.toBeInTheDocument();
  });
});
