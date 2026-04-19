import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { EntryCard } from '../EntryCard';
import type { DevstackEntry } from '../../types/devstack';

function makeEntry(overrides: Partial<DevstackEntry> = {}): DevstackEntry {
  return {
    id: '1',
    name: 'test-entry',
    description: 'desc',
    type: 'skill',
    install_method: 'github',
    url: 'https://github.com/a/b/blob/main/x.md',
    package: null,
    package_version: null,
    required: false,
    origin: 'internal',
    tech: [],
    active: true,
    github_sha: 'abcdef1234567',
    latest_package_version: null,
    featured: false,
    install_count: 0,
    last_installed_at: null,
    deprecated: false,
    deprecation_message: null,
    vulnerabilities: null,
    created_at: '2026-04-19T00:00:00Z',
    updated_at: '2026-04-19T00:00:00Z',
    ...overrides,
  };
}

function renderCard(entry: DevstackEntry) {
  return render(
    <MemoryRouter>
      <EntryCard entry={entry} onClick={vi.fn()} />
    </MemoryRouter>
  );
}

describe('EntryCard badges', () => {
  it('shows critical vulnerability badge when critical > 0', () => {
    renderCard(makeEntry({
      vulnerabilities: { critical: 2, high: 0, moderate: 0, low: 0, advisories: [] },
    }));
    expect(screen.getByText(/2 critical/i)).toBeInTheDocument();
  });

  it('shows high vulnerability badge when high > 0 and no critical', () => {
    renderCard(makeEntry({
      vulnerabilities: { critical: 0, high: 3, moderate: 0, low: 0, advisories: [] },
    }));
    expect(screen.getByText(/3 high/i)).toBeInTheDocument();
  });

  it('shows no vulnerability badge when counts are zero', () => {
    renderCard(makeEntry({
      vulnerabilities: { critical: 0, high: 0, moderate: 0, low: 0, advisories: [] },
    }));
    expect(screen.queryByText(/critical|high/i)).not.toBeInTheDocument();
  });

  it('shows deprecated badge when deprecated is true', () => {
    renderCard(makeEntry({ deprecated: true, deprecation_message: 'use foo' }));
    expect(screen.getByText(/deprecated/i)).toBeInTheDocument();
  });

  it('shows install count chip with count when install_count > 0', () => {
    renderCard(makeEntry({ install_count: 12 }));
    expect(screen.getByTestId('install-chip')).toHaveTextContent('12');
  });

  it('hides install count chip when install_count is 0', () => {
    renderCard(makeEntry({ install_count: 0 }));
    expect(screen.queryByTestId('install-chip')).not.toBeInTheDocument();
  });
});
