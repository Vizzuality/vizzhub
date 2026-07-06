import { Outlet } from 'react-router-dom';
import { ProjectsHubTabs } from './ProjectsHubTabs';

export default function ProjectsHubLayout(): JSX.Element {
  return (
    <div className="space-y-4">
      <ProjectsHubTabs />
      <Outlet />
    </div>
  );
}
