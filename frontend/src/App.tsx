import { Routes, Route, Link } from 'react-router-dom';
import { LayoutDashboard, FolderKanban, Settings } from 'lucide-react';
import ProjectList from './pages/ProjectList';
import ProjectDetail from './pages/ProjectDetail';
import SettingsPage from './pages/Settings';

function App(): JSX.Element {
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-gray-200 p-6">
        <h1 className="text-xl font-bold text-primary-600 mb-8">
          Project Scorecard
        </h1>
        <nav className="space-y-2">
          <Link
            to="/"
            className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <LayoutDashboard className="w-5 h-5" />
            Dashboard
          </Link>
          <Link
            to="/projects"
            className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <FolderKanban className="w-5 h-5" />
            Projects
          </Link>
          <Link
            to="/settings"
            className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100"
          >
            <Settings className="w-5 h-5" />
            Settings
          </Link>
        </nav>
      </aside>

      <main className="flex-1 p-8">
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/projects" element={<ProjectList />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
