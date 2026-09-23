import { describe, expect, it } from 'vitest';
import { safeRedirectPath } from '../safeRedirect';

describe('safeRedirectPath', () => {
  it('keeps same-origin relative paths', () => {
    expect(safeRedirectPath('/tracker/periods?month=8')).toBe('/tracker/periods?month=8');
  });

  it.each(['//evil.com', '/\\evil.com', '\\\\evil.com', 'https://evil.com', 'evil.com', ''])(
    'falls back to root for %s',
    (target) => {
      expect(safeRedirectPath(target)).toBe('/');
    }
  );

  it('falls back to root when target is missing', () => {
    expect(safeRedirectPath(undefined)).toBe('/');
  });
});
