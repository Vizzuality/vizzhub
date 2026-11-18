import { useCallback } from 'react';

/**
 * Callback ref that focuses the element once, when it mounts. Used for inline
 * editors that appear because the user asked to edit, instead of `autoFocus`.
 */
export function useFocusOnMount<T extends HTMLElement>(): (element: T | null) => void {
  return useCallback((element: T | null) => {
    element?.focus();
  }, []);
}
