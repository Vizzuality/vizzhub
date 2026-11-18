import { describe, expect, it } from 'vitest';

import { toDisplayString } from '../formatters';

describe('toDisplayString', () => {
  it('keeps strings as they are', () => {
    expect(toDisplayString('abc')).toBe('abc');
  });

  it('formats numbers and booleans', () => {
    expect(toDisplayString(42)).toBe('42');
    expect(toDisplayString(false)).toBe('false');
  });

  it('returns an empty string for null and undefined', () => {
    expect(toDisplayString(null)).toBe('');
    expect(toDisplayString(undefined)).toBe('');
  });

  it('serializes objects as JSON instead of [object Object]', () => {
    expect(toDisplayString({ a: 1 })).toBe('{"a":1}');
    expect(toDisplayString([1, 2])).toBe('[1,2]');
  });
});
