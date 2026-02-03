import { Link, Outlet, useLocation } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
import { VizzualityLogo } from './VizzualityLogo';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Menu } from 'lucide-react';

export function AppLayout() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          {/* Logo */}
          <Link to="/projects" className="flex items-center gap-3">
            <VizzualityLogo className="h-8 w-auto" />
            <div className="hidden sm:block h-6 w-px bg-border" />
            <span className="text-xl font-semibold hidden sm:inline">Project Scorecard</span>
          </Link>

          {/* Right side: Navigation + Theme Toggle */}
          <div className="flex items-center gap-2">
            {/* Desktop Navigation */}
            <div className="hidden md:flex gap-1">
              <Link to="/projects">
                <Button
                  variant={isActive('/projects') ? 'secondary' : 'ghost'}
                >
                  Projects
                </Button>
              </Link>
              <Link to="/global">
                <Button
                  variant={isActive('/global') ? 'secondary' : 'ghost'}
                >
                  Global
                </Button>
              </Link>
              <Link to="/admin">
                <Button
                  variant={location.pathname.startsWith('/admin') ? 'secondary' : 'ghost'}
                >
                  Admin
                </Button>
              </Link>
            </div>

            <ThemeToggle />

            {/* Mobile Navigation */}
            <div className="md:hidden">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <Menu className="h-5 w-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem asChild>
                    <Link to="/projects">Projects</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/global">Global</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/admin">Admin</Link>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="container mx-auto py-6 px-4">
        <Outlet />
      </main>
    </div>
  );
}
