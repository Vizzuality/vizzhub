import { Link, useLocation } from 'react-router-dom';
import type { To } from 'react-router-dom';
import { useNavigationGuard } from '@/core/contexts/NavigationGuardContext';
import {
  BarChart3,
  BookOpen,
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
  TrendingUp,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { usePermission, Action } from '@/core/permissions';
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
  useSidebar,
} from '@/shared/components/ui/sidebar';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/shared/components/ui/collapsible';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';

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
  { to: '/admin/notifications/custom', label: 'Custom' },
] as const;

const TRACKER_TABS = [
  { to: '/admin/tracker/periods', label: 'Reporting Periods' },
  { to: '/admin/tracker/invoices', label: 'Invoices' },
  { to: '/admin/tracker/moods', label: 'Moods' },
  { to: '/admin/tracker/rates', label: 'Rates' },
] as const;

const ISO_TABS = [
  { to: '/iso/snapshots', label: 'Access Control' },
] as const;

const CAPACITY_TABS = [
  { to: '/capacity/insights', label: 'Insights' },
  { to: '/capacity/allocation', label: 'Allocation' },
  { to: '/capacity/planner', label: 'Planner' },
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

interface SubItem {
  readonly to: string;
  readonly label: string;
}

function CollapsibleMenuItem({
  icon: Icon,
  label,
  isActive,
  items,
}: {
  readonly icon: React.ComponentType;
  readonly label: string;
  readonly isActive: boolean;
  readonly items: readonly SubItem[];
}): JSX.Element {
  const { state, isMobile } = useSidebar();
  const location = useLocation();

  if (!isMobile && state === 'collapsed') {
    return (
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton isActive={isActive} tooltip={label}>
              <Icon />
              <span>{label}</span>
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="start" sideOffset={4}>
            {items.map(({ to, label: itemLabel }) => (
              <DropdownMenuItem key={to} asChild>
                <GuardedLink to={to}>{itemLabel}</GuardedLink>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    );
  }

  return (
    <Collapsible
      key={isActive ? `${label}-open` : `${label}-closed`}
      defaultOpen={isActive}
      className="group/collapsible"
    >
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton isActive={isActive} tooltip={label}>
            <Icon />
            <span>{label}</span>
            <ChevronRight className="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {items.map(({ to, label: itemLabel }) => (
              <SidebarMenuSubItem key={to}>
                <SidebarMenuSubButton asChild isActive={location.pathname === to || location.pathname.startsWith(to)}>
                  <GuardedLink to={to}>{itemLabel}</GuardedLink>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  );
}

export function AppSidebar(): JSX.Element {
  const location = useLocation();
  const { theme, setTheme } = useTheme();

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const isAdmin = bypassAuth || canAdmin;

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

              <CollapsibleMenuItem
                icon={TrendingUp}
                label="Capacity"
                isActive={isActive('/capacity')}
                items={CAPACITY_TABS}
              />

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  isActive={isActive('/playbook')}
                  tooltip="Playbook"
                >
                  <GuardedLink to="/playbook">
                    <BookOpen />
                    <span>Playbook</span>
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
                <CollapsibleMenuItem
                  icon={Shield}
                  label="ISO"
                  isActive={isActive('/iso')}
                  items={ISO_TABS}
                />
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

                  <CollapsibleMenuItem
                    icon={Bell}
                    label="Notifications"
                    isActive={location.pathname.startsWith('/admin/notifications')}
                    items={NOTIFICATION_TABS}
                  />

                  <CollapsibleMenuItem
                    icon={Clock}
                    label="Tracker"
                    isActive={location.pathname.startsWith('/admin/tracker')}
                    items={TRACKER_TABS}
                  />
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
