import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useLocalStorage } from '@/shared/hooks/useLocalStorage';

describe('useLocalStorage', () => {
  beforeEach(() => localStorage.clear());

  it('returns the initial value when storage is empty', () => {
    const { result } = renderHook(() => useLocalStorage('k', 'init'));
    expect(result.current[0]).toBe('init');
  });

  it('hydrates from existing storage', () => {
    localStorage.setItem('arr', JSON.stringify(['a', 'b']));
    const { result } = renderHook(() => useLocalStorage<string[]>('arr', []));
    expect(result.current[0]).toEqual(['a', 'b']);
  });

  it('persists updates to localStorage', () => {
    const { result } = renderHook(() => useLocalStorage<number>('n', 0));
    act(() => result.current[1](5));
    expect(result.current[0]).toBe(5);
    expect(JSON.parse(localStorage.getItem('n') as string)).toBe(5);
  });

  it('supports updater functions', () => {
    const { result } = renderHook(() => useLocalStorage<boolean>('flag', false));
    act(() => result.current[1]((prev) => !prev));
    expect(result.current[0]).toBe(true);
  });

  it('falls back to the initial value on malformed JSON', () => {
    localStorage.setItem('bad', '{not json');
    const { result } = renderHook(() => useLocalStorage('bad', 'fallback'));
    expect(result.current[0]).toBe('fallback');
  });
});
