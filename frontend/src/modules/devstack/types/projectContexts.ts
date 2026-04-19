export interface ProjectContext {
  id: string;
  slug: string;
  project_id: string;
  project_name: string | null;
  description: string | null;
  github_seeded?: boolean | null;
  github_error?: string | null;
}

export interface ProjectContextCreate {
  slug: string;
  project_id: string;
  description: string | null;
  // Second-stage submit after the user confirms linking to an already-existing
  // <slug>/CLAUDE.md in GitHub. Skips both the pre-check and the seed write.
  associate_existing?: boolean;
}

// Shape of the 409 "file already exists" response body sent by the backend
// when it detects <slug>/CLAUDE.md already lives in the private repo.
export interface GithubFileExistsDetail {
  code: 'github_file_exists';
  slug: string;
  message: string;
}

export interface ProjectContextUpdate {
  description: string | null;
}
