import { Link, useLocation } from 'react-router-dom';
import type { To } from 'react-router-dom';
import { useNavigationGuard } from '@/core/contexts/NavigationGuardContext';
import {
  BarChart3,
  ClipboardList,
  FolderKanban,
  Shield,
  Globe,
  SlidersHorizontal,
  Plug,
  Bell,
  Clock,
  Cog,
  Users,
  Moon,
  Sun,
  ChevronRight,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { useAuth } from '@/core/hooks/useAuth';
import { VizzualityLogo } from './VizzualityLogo';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarSeparator,
} from '@/shared/components/ui/sidebar';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/components/ui/collapsible';

const ADMIN_ITEMS = [
  { to: '/admin/scorecard-parameters', label: 'Parameters', icon: SlidersHorizontal },
  { to: '/admin/integrations', label: 'Integrations', icon: Plug },
  { to: '/admin/jobs', label: 'Jobs', icon: Cog },
  { to: '/admin/users', label: 'Users', icon: Users },
] as const;

const NOTIFICATION_TABS = [
  { to: '/admin/notifications/log', label: 'Alert Log' },
  { to: '/admin/notifications/silences', label: 'Active Silences' },
  { to: '/admin/notifications/config', label: 'Configuration' },
  { to: '/admin/notifications/stats', label: 'Statistics' },
] as const;

const TRACKER_TABS = [
  { to: '/admin/tracker/periods', label: 'Reporting Periods' },
  { to: '/admin/tracker/invoices', label: 'Invoices' },
] as const;


function GuardedLink({
  to,
  children,
  className,
}: {
  readonly to: To;
  readonly children: React.ReactNode;
  readonly className?: string;
}): JSX.Element {
  const { confirmNavigation } = useNavigationGuard();

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>): void => {
    if (!confirmNavigation()) {
      e.preventDefault();
    }
  };

  return (
    <Link to={to} className={className} onClick={handleClick}>
      {children}
    </Link>
  );
}

export function AppSidebar(): JSX.Element {
  const location = useLocation();
  const auth = useAuth();
  const { theme, setTheme } = useTheme();

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const isAdmin = bypassAuth || auth.user?.role === 'admin';

  const isActive = (path: string): boolean => {
    if (path === '/scorecard') {
      return location.pathname === '/scorecard' || location.pathname.startsWith('/scorecard/');
    }
    if (path === '/projects') {
      return location.pathname === '/projects' || location.pathname.startsWith('/projects/');
    }
    return location.pathname.startsWith(path);
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="p-4">
        <GuardedLink to="/" className="flex items-center gap-2">
          <VizzualityLogo className="h-6 w-auto shrink-0 group-data-[collapsible=icon]:hidden" />
        </GuardedLink>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  isActive={isActive('/projects')}
                  tooltip="Projects"
                >
                  <GuardedLink to="/projects">
                    <FolderKanban />
                    <span>Projects</span>
                  </GuardedLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  isActive={isActive('/scorecard')}
                  tooltip="Scorecard"
                >
                  <GuardedLink to="/scorecard">
                    <BarChart3 />
                    <span>Scorecard</span>
                  </GuardedLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  isActive={isActive('/tracker/my-report')}
                  tooltip="My Report"
                >
                  <GuardedLink to="/tracker/my-report">
                    <ClipboardList />
                    <span>My Report</span>
                  </GuardedLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              {isAdmin && (
                <SidebarMenuItem>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive('/admin/global-scores')}
                    tooltip="Global Scores"
                  >
                    <GuardedLink to="/admin/global-scores">
                      <Globe />
                      <span>Global Scores</span>
                    </GuardedLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}

              {isAdmin && (
                <Collapsible
                  key={isActive('/iso') ? 'iso-open' : 'iso-closed'}
                  defaultOpen={isActive('/iso')}
                  className="group/collapsible"
                >
                  <SidebarMenuItem>
                    <CollapsibleTrigger asChild>
                      <SidebarMenuButton
                        isActive={isActive('/iso')}
                        tooltip="ISO"
                      >
                        <Shield />
                        <span>ISO</span>
                        <ChevronRight className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90" />
                      </SidebarMenuButton>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <SidebarMenuSub>
                        <SidebarMenuSubItem>
                          <SidebarMenuSubButton
                            asChild
                            isActive={isActive('/iso/snapshots')}
                          >
                            <GuardedLink to="/iso/snapshots">
                              <span>Access Control</span>
                            </GuardedLink>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      </SidebarMenuSub>
                    </CollapsibleContent>
                  </SidebarMenuItem>
                </Collapsible>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {isAdmin && (
          <>
            <SidebarSeparator />
            <SidebarGroup>
              <SidebarGroupLabel>Administration</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {ADMIN_ITEMS.map(({ to, label, icon: Icon }) => (
                    <SidebarMenuItem key={to}>
                      <SidebarMenuButton
                        asChild
                        isActive={location.pathname === to}
                        tooltip={label}
                      >
                        <GuardedLink to={to}>
                          <Icon />
                          <span>{label}</span>
                        </GuardedLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}

                  <Collapsible
                    key={location.pathname.startsWith('/admin/notifications') ? 'notif-open' : 'notif-closed'}
                    defaultOpen={location.pathname.startsWith('/admin/notifications')}
                    className="group/collapsible"
                  >
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton
                          isActive={location.pathname.startsWith('/admin/notifications')}
                          tooltip="Notifications"
                        >
                          <Bell />
                          <span>Notifications</span>
                          <ChevronRight className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90" />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {NOTIFICATION_TABS.map(({ to, label }) => (
                            <SidebarMenuSubItem key={to}>
                              <SidebarMenuSubButton
                                asChild
                                isActive={location.pathname === to}
                              >
                                <GuardedLink to={to}>{label}</GuardedLink>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>

                  <Collapsible
                    key={location.pathname.startsWith('/admin/tracker') ? 'tracker-open' : 'tracker-closed'}
                    defaultOpen={location.pathname.startsWith('/admin/tracker')}
                    className="group/collapsible"
                  >
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton
                          isActive={location.pathname.startsWith('/admin/tracker')}
                          tooltip="Tracker"
                        >
                          <Clock />
                          <span>Tracker</span>
                          <ChevronRight className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90" />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {TRACKER_TABS.map(({ to, label }) => (
                            <SidebarMenuSubItem key={to}>
                              <SidebarMenuSubButton
                                asChild
                                isActive={location.pathname.startsWith(to)}
                              >
                                <GuardedLink to={to}>{label}</GuardedLink>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>

      <SidebarSeparator />

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              tooltip={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            >
              <Sun className="rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
              <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>

        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
