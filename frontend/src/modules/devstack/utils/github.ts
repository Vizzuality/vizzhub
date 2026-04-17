/**
 * Convert a GitHub blob URL to a raw.githubusercontent.com URL.
 * If already raw or unrecognized, returns the original URL.
 */
export function toRawGithubUrl(url: string): string {
  const blobMatch = url.match(
    /^https?:\/\/github\.com\/([^/]+)\/([^/]+)\/blob\/(.+)$/
  );
  if (blobMatch) {
    const [, owner, repo, refAndPath] = blobMatch;
    return `https://raw.githubusercontent.com/${owner}/${repo}/${refAndPath}`;
  }
  return url;
}
