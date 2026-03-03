import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
import { VizzualityLogo } from './VizzualityLogo';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/shared/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { LogOut, Menu } from 'lucide-react';

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const auth = useAuth();

  const isAdmin = auth.user?.role === 'admin';

  const isActive = (path: string): boolean => location.pathname === path;

  const getPageTitle = (): string => {
    if (location.pathname.startsWith('/admin')) return 'Admin';
    if (location.pathname.startsWith('/iso')) return 'ISO';
    return 'Scorecard';
  };

  const handleLogout = async (): Promise<void> => {
    await auth.logout();
    navigate('/login');
  };

  const userInitials = [auth.user?.first_name, auth.user?.last_name]
    .filter(Boolean)
    .map((n) => n![0])
    .join('')
    .toUpperCase() || '?';

  return (
    <div className="min-h-screen">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <Link to="/scorecard">
              <VizzualityLogo className="h-8 w-auto" />
            </Link>
            <div className="hidden sm:block h-6 w-px bg-border" />
            <span className="text-xl font-semibold hidden sm:inline">{getPageTitle()}</span>
          </div>

          {/* Right side: Navigation + Theme Toggle */}
          <div className="flex items-center gap-2">
            {/* Desktop Navigation */}
            <div className="hidden md:flex gap-1">
              <Link to="/scorecard">
                <Button
                  variant={isActive('/scorecard') ? 'secondary' : 'ghost'}
                >
                  Scorecard
                </Button>
              </Link>
              {isAdmin && (
                <Link to="/iso">
                  <Button
                    variant={location.pathname.startsWith('/iso') ? 'secondary' : 'ghost'}
                  >
                    ISO
                  </Button>
                </Link>
              )}
              {isAdmin && (
                <Link to="/admin">
                  <Button
                    variant={location.pathname.startsWith('/admin') ? 'secondary' : 'ghost'}
                  >
                    Admin
                  </Button>
                </Link>
              )}
            </div>

            <ThemeToggle />

            {/* User Menu (desktop) */}
            {auth.isAuthenticated && (
              <div className="hidden md:block">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="rounded-full">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src={auth.user?.picture ?? undefined} alt={auth.user?.first_name ?? 'User'} />
                        <AvatarFallback className="text-xs text-muted-foreground">{userInitials}</AvatarFallback>
                      </Avatar>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel className="font-normal">
                      <div className="flex flex-col gap-1">
                        <p className="text-sm font-medium leading-none">
                          {[auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' ')}
                        </p>
                        <p className="text-xs leading-none text-muted-foreground">
                          {auth.user?.email}
                        </p>
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={handleLogout}>
                      <LogOut className="mr-2 h-4 w-4" />
                      Log out
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}

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
                    <Link to="/scorecard">Scorecard</Link>
                  </DropdownMenuItem>
                  {isAdmin && (
                    <DropdownMenuItem asChild>
                      <Link to="/iso">ISO</Link>
                    </DropdownMenuItem>
                  )}
                  {isAdmin && (
                    <DropdownMenuItem asChild>
                      <Link to="/admin">Admin</Link>
                    </DropdownMenuItem>
                  )}
                  {auth.isAuthenticated && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={handleLogout}>
                        <LogOut className="mr-2 h-4 w-4" />
                        Log out
                      </DropdownMenuItem>
                    </>
                  )}
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
