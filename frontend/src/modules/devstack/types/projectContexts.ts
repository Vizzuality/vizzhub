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
}

export interface ProjectContextUpdate {
  description: string | null;
}
