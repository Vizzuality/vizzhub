import { useCallback, useState } from 'react';

type Setter<T> = (value: T | ((prev: T) => T)) => void;

/**
 * State backed by `localStorage`, JSON-serialised under `key`. Reads lazily on
 * mount and writes on every update. Storage failures (unavailable, quota,
 * malformed JSON) fall back to `initialValue` and are swallowed so the UI never
 * breaks because persistence is unavailable.
 */
export function useLocalStorage<T>(key: string, initialValue: T): [T, Setter<T>] {
  const [stored, setStored] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? initialValue : (JSON.parse(raw) as T);
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback<Setter<T>>(
    (value) => {
      setStored((prev) => {
        const next = value instanceof Function ? value(prev) : value;
        try {
          localStorage.setItem(key, JSON.stringify(next));
        } catch {
          // Persistence is best-effort; keep the in-memory value regardless.
        }
        return next;
      });
    },
    [key],
  );

  return [stored, setValue];
}
