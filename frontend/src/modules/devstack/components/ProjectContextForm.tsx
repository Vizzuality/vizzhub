import type { ProjectContext } from '../types/projectContexts';

interface ProjectContextFormProps {
  readonly context: ProjectContext | null;
  readonly onClose: () => void;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ProjectContextForm(_props: ProjectContextFormProps): JSX.Element {
  return <></>;
}
