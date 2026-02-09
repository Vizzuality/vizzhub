import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useUrlState, urlCodecs } from '../useUrlState';

function createWrapper(initialEntries: string[] = ['/']) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return MemoryRouter({ initialEntries, children });
  };
}

const stringSchema = {
  search: { defaultValue: '' },
  status: { defaultValue: 'all' },
};

const numberSchema = {
  year: { defaultValue: 2026 },
  month: { defaultValue: 1 },
};

const booleanSchema = {
  compact: { defaultValue: false, codec: urlCodecs.boolean },
};

describe('useUrlState', () => {
  it('returns default values when no params in URL', () => {
    const { result } = renderHook(() => useUrlState(stringSchema), {
      wrapper: createWrapper(),
    });
    expect(result.current.state).toEqual({ search: '', status: 'all' });
  });

  it('reads initial values from URL', () => {
    const { result } = renderHook(() => useUrlState(stringSchema), {
      wrapper: createWrapper(['/?search=hello&status=active']),
    });
    expect(result.current.state).toEqual({ search: 'hello', status: 'active' });
  });

  it('reads number params from URL', () => {
    const { result } = renderHook(() => useUrlState(numberSchema), {
      wrapper: createWrapper(['/?year=2025&month=6']),
    });
    expect(result.current.state).toEqual({ year: 2025, month: 6 });
  });

  it('reads boolean params from URL', () => {
    const { result } = renderHook(() => useUrlState(booleanSchema), {
      wrapper: createWrapper(['/?compact=1']),
    });
    expect(result.current.state).toEqual({ compact: true });
  });

  it('setState updates state', () => {
    const { result } = renderHook(() => useUrlState(stringSchema), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.setState({ search: 'test' });
    });

    expect(result.current.state.search).toBe('test');
  });

  it('setState removes params at default value', () => {
    const { result } = renderHook(() => useUrlState(stringSchema), {
      wrapper: createWrapper(['/?search=hello']),
    });

    act(() => {
      result.current.setState({ search: '' });
    });

    expect(result.current.state.search).toBe('');
  });

  it('resetState clears all params to defaults', () => {
    const { result } = renderHook(() => useUrlState(stringSchema), {
      wrapper: createWrapper(['/?search=hello&status=active']),
    });

    act(() => {
      result.current.resetState();
    });

    expect(result.current.state).toEqual({ search: '', status: 'all' });
  });

  it('partial setState preserves other params', () => {
    const { result } = renderHook(() => useUrlState(numberSchema), {
      wrapper: createWrapper(['/?year=2025&month=6']),
    });

    act(() => {
      result.current.setState({ month: 7 });
    });

    expect(result.current.state).toEqual({ year: 2025, month: 7 });
  });
});
