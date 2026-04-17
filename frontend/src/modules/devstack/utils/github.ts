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
