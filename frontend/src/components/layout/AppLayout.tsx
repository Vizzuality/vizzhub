import { Link, Outlet, useLocation } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
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
          {/* Logo and Desktop Navigation */}
          <div className="flex items-center gap-6">
            <Link to="/projects" className="text-xl font-semibold">
              Project Scorecard
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex gap-1">
              <Link to="/projects">
                <Button
                  variant={isActive('/projects') ? 'secondary' : 'ghost'}
                >
                  Projects
                </Button>
              </Link>
              <Link to="/settings">
                <Button
                  variant={isActive('/settings') ? 'secondary' : 'ghost'}
                >
                  Settings
                </Button>
              </Link>
            </div>
          </div>

          {/* Right side: Theme Toggle + Mobile Menu */}
          <div className="flex items-center gap-2">
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
                    <Link to="/settings">Settings</Link>
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
