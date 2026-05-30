import { Link, useLocation } from 'react-router-dom';
import type { To } from 'react-router-dom';
import { useNavigationGuard } from '@/core/contexts/NavigationGuardContext';
import {
  BarChart3,
  Blocks,
  BookOpen,
  CalendarDays,
  ClipboardList,
  Coins,
  FolderKanban,
  ListTodo,
  Shield,
  Globe,
  SlidersHorizontal,
  Plug,
  Bell,
  Clock,
  Cog,
  HardDrive,
  Users,
  MessageSquare,
  Moon,
  Sun,
  ChevronRight,
  TrendingUp,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { useAnyPermission, usePermission, Action } from '@/core/permissions';
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
  { to: '/admin/assets', label: 'Assets', icon: HardDrive },
  { to: '/admin/jobs', label: 'Jobs', icon: Cog },
  { to: '/admin/commands', label: 'Command Queue', icon: ListTodo },
  { to: '/admin/users', label: 'Users', icon: Users },
] as const;

const ACCRUAL_TABS = [
  { to: '/admin/accrual', label: 'Grid' },
  { to: '/admin/accrual/periods', label: 'Periods' },
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

const ISO_ADMIN_TABS = [
  { to: '/admin/iso/notes', label: 'Notes' },
] as const;

const ISO_TABS_ADMIN = [
  { to: '/iso/docs', label: 'Documentation' },
  { to: '/iso/snapshots', label: 'Access Control' },
] as const;

const CAPACITY_TABS = [
  { to: '/capacity/insights', label: 'Insights' },
  { to: '/capacity/allocation', label: 'Allocation' },
  { to: '/capacity/planner', label: 'Planner' },
] as const;

const EVENTS_TABS = [
  { to: '/events', label: 'List' },
  { to: '/events/dashboard', label: 'Dashboard' },
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
  const { resolvedTheme, setTheme } = useTheme();
  const { state, toggleSidebar } = useSidebar();

  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const canTrackerAdmin = useAnyPermission(
    Action.ADMIN_USERS,
    Action.TRACKER_MANAGE_ALL_REPORTS,
  );
  const isAdmin = bypassAuth || canAdmin;
  const showTrackerAdmin = bypassAuth || canTrackerAdmin;
  const showAdminSection = isAdmin || showTrackerAdmin;

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
      <SidebarHeader className="p-4 transition-[padding] duration-200 ease-linear group-data-[collapsible=icon]:px-0">
        <GuardedLink to="/" className="flex items-center gap-2 group-data-[collapsible=icon]:justify-center">
          <VizzualityLogo className="h-6 w-[6.29rem] shrink-0 transition-[width] duration-200 ease-linear group-data-[collapsible=icon]:w-[1.1rem]" />
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

              <CollapsibleMenuItem
                icon={CalendarDays}
                label="Events"
                isActive={isActive('/events')}
                items={EVENTS_TABS}
              />

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  isActive={isActive('/devstack')}
                  tooltip="DevStack"
                >
                  <GuardedLink to="/devstack">
                    <Blocks />
                    <span>DevStack</span>
                  </GuardedLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  isActive={isActive('/scorecard/global')}
                  tooltip="Global Scores"
                >
                  <GuardedLink to="/scorecard/global">
                    <Globe />
                    <span>Global Scores</span>
                  </GuardedLink>
                </SidebarMenuButton>
              </SidebarMenuItem>

              {isAdmin ? (
                <CollapsibleMenuItem
                  icon={Shield}
                  label="ISO"
                  isActive={isActive('/iso')}
                  items={ISO_TABS_ADMIN}
                />
              ) : (
                <SidebarMenuItem>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive('/iso/docs')}
                    tooltip="ISO Docs"
                  >
                    <GuardedLink to="/iso/docs">
                      <Shield />
                      <span>ISO Docs</span>
                    </GuardedLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {showAdminSection && (
          <>
            <SidebarSeparator />
            <SidebarGroup>
              <SidebarGroupLabel>Administration</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {isAdmin &&
                    ADMIN_ITEMS.map(({ to, label, icon: Icon }) => (
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

                  {isAdmin && (
                    <CollapsibleMenuItem
                      icon={Bell}
                      label="Notifications"
                      isActive={location.pathname.startsWith('/admin/notifications')}
                      items={NOTIFICATION_TABS}
                    />
                  )}

                  {showTrackerAdmin && (
                    <CollapsibleMenuItem
                      icon={Clock}
                      label="Tracker"
                      isActive={location.pathname.startsWith('/admin/tracker')}
                      items={TRACKER_TABS}
                    />
                  )}

                  {isAdmin && (
                    <CollapsibleMenuItem
                      icon={MessageSquare}
                      label="ISO"
                      isActive={location.pathname.startsWith('/admin/iso')}
                      items={ISO_ADMIN_TABS}
                    />
                  )}

                  {isAdmin && (
                    <CollapsibleMenuItem
                      icon={Coins}
                      label="Accrual"
                      isActive={location.pathname.startsWith('/admin/accrual')}
                      items={ACCRUAL_TABS}
                    />
                  )}
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
              onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
              tooltip={resolvedTheme === 'dark' ? 'Light mode' : 'Dark mode'}
            >
              <Sun className="rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
              <span>{resolvedTheme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => toggleSidebar()}
              tooltip={state === 'collapsed' ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {state === 'collapsed'
                ? <PanelLeftOpen />
                : <PanelLeftClose />}
              <span>Collapse sidebar</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
