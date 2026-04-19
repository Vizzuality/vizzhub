export interface ProjectContext {
  id: string;
  slug: string;
  project_id: string;
  project_name: string | null;
  description: string | null;
  // Present only on the create (POST) response. Null on list/get/update.
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
