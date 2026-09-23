/**
 * Restrict post-login redirects to same-origin relative paths. Browsers treat
 * `//host` and `/\host` as protocol-relative URLs, so both are rejected.
 */
export function safeRedirectPath(target: string | undefined): string {
  if (!target?.startsWith('/') || target.startsWith('//') || target.startsWith('/\\')) {
    return '/';
  }
  return target;
}
