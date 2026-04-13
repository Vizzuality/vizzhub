export interface IsoDocNote {
  id: string;
  node_id: string;
  content: string;
  done: boolean;
  done_at: string | null;
  done_by_id: string | null;
  done_by_name: string | null;
  created_by_id: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminIsoDocNote extends IsoDocNote {
  node_title: string;
  node_slug: string | null;
}

export interface NoteCreate {
  content: string;
}

export interface NoteUpdate {
  content?: string;
  done?: boolean;
}
