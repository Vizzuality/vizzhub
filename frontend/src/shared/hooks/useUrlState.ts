import { useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

interface UrlCodec<T> {
  encode: (value: T) => string;
  decode: (raw: string) => T;
}

export const urlCodecs = {
  string: { encode: (v: string): string => v, decode: (r: string): string => r } as UrlCodec<string>,
  number: { encode: (v: number): string => String(v), decode: (r: string): number => Number(r) } as UrlCodec<number>,
  boolean: { encode: (v: boolean): string => (v ? '1' : '0'), decode: (r: string): boolean => r === '1' } as UrlCodec<boolean>,
};

interface ParamDef<T> {
  defaultValue: T;
  codec?: UrlCodec<T>;
}

type UrlStateSchema = Record<string, ParamDef<unknown>>;

type SchemaState<S extends UrlStateSchema> = {
  [K in keyof S]: S[K] extends ParamDef<infer T> ? T : never;
};

type PartialSchemaState<S extends UrlStateSchema> = Partial<SchemaState<S>>;

interface UseUrlStateReturn<S extends UrlStateSchema> {
  state: SchemaState<S>;
  setState: (patch: PartialSchemaState<S>, options?: { replace?: boolean }) => void;
  resetState: () => void;
}

function getCodec<T>(def: ParamDef<T>): UrlCodec<T> {
  if (def.codec) return def.codec;
  const t = typeof def.defaultValue;
  if (t === 'number') return urlCodecs.number as unknown as UrlCodec<T>;
  if (t === 'boolean') return urlCodecs.boolean as unknown as UrlCodec<T>;
  return urlCodecs.string as unknown as UrlCodec<T>;
}

export function useUrlState<S extends UrlStateSchema>(
  schema: S,
): UseUrlStateReturn<S> {
  const [searchParams, setSearchParams] = useSearchParams();
  const schemaRef = useRef(schema);
  schemaRef.current = schema;

  const state = useMemo(() => {
    const result = {} as Record<string, unknown>;
    for (const [key, def] of Object.entries(schemaRef.current)) {
      const raw = searchParams.get(key);
      if (raw === null) {
        result[key] = def.defaultValue;
      } else {
        const codec = getCodec(def as ParamDef<unknown>);
        result[key] = codec.decode(raw);
      }
    }
    return result as SchemaState<S>;
  }, [searchParams]);

  const setState = useCallback(
    (patch: PartialSchemaState<S>, options?: { replace?: boolean }) => {
      const replace = options?.replace ?? true;
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(patch)) {
          const def = schemaRef.current[key];
          if (!def) continue;
          const codec = getCodec(def as ParamDef<unknown>);
          const encoded = codec.encode(value as never);
          const defaultEncoded = codec.encode(def.defaultValue as never);
          if (encoded === defaultEncoded) {
            next.delete(key);
          } else {
            next.set(key, encoded);
          }
        }
        return next;
      }, { replace });
    },
    [setSearchParams],
  );

  const resetState = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of Object.keys(schemaRef.current)) {
        next.delete(key);
      }
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  return { state, setState, resetState };
}
