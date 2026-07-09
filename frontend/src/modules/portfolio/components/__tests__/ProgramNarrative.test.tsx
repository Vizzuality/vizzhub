import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgramNarrative } from '../ProgramNarrative';
import type { ProgramProfile } from '../../types/portfolio';

function profileWith(websiteUrl: string): ProgramProfile {
  return {
    objective: null, short_description: null, web_copy: null,
    website_url: websiteUrl, impact_story: null, main_partner: null,
    stage: null, on_website: false,
  };
}

describe('ProgramNarrative', () => {
  it('links http(s) website URLs', () => {
    render(<ProgramNarrative profile={profileWith('https://example.org')} />);
    expect(screen.getByRole('link', { name: /example\.org/ })).toHaveAttribute(
      'href',
      'https://example.org',
    );
  });

  it('renders non-http schemes as plain text, never as a link', () => {
    render(<ProgramNarrative profile={profileWith('javascript:alert(1)')} />);
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
