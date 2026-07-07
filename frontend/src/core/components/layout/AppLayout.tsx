import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { LogOut, FileText, UserRoundCog, UserX } from 'lucide-react';
import { AppSidebar } from './AppSidebar';
import { ImpersonateDialog } from './ImpersonateDialog';
import { useAuth } from '@/core/hooks/useAuth';
import {
  SidebarInset,
  SidebarProvider,
} from '@/shared/components/ui/sidebar';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Button } from '@/shared/components/ui/button';
import { useReportingPeriods } from '@/modules/tracker/public';
import { getFullName, getInitials } from '@/utils/formatters';
import { usePermission, Action } from '@/core/permissions';

export function AppLayout(): JSX.Element {
  const auth = useAuth();
  const navigate = useNavigate();
  const canAdmin = usePermission(Action.ADMIN_USERS);
  const [impersonateOpen, setImpersonateOpen] = useState(false);

  const handleLogout = async (): Promise<void> => {
    await auth.logout();
    navigate('/login');
  };

  const handleStopImpersonating = async (): Promise<void> => {
    try {
      await auth.stopImpersonating();
      window.location.reload();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (err instanceof Error ? err.message : 'Failed to stop impersonating');
      console.error('Failed to stop impersonating:', err);
      alert(detail);
    }
  };

  const { data: periods } = useReportingPeriods();
  const activePeriod = periods?.find((p) => p.status === 'active');

  const userInitials = getInitials(auth.user?.first_name, auth.user?.last_name);

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="min-w-0 overflow-x-hidden">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4">
          <div className="ml-auto flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <Avatar className={`h-8 w-8 ${auth.isImpersonating ? 'ring-2 ring-orange-500' : ''}`}>
                    <AvatarImage
                      src={auth.user?.picture ?? undefined}
                      alt={auth.user?.first_name ?? 'User'}
                    />
                    <AvatarFallback className="text-xs text-muted-foreground">
                      {userInitials}
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col gap-1">
                    {auth.isImpersonating && (
                      <p className="text-xs font-medium text-orange-500">
                        Viewing as:
                      </p>
                    )}
                    <p className="text-sm font-medium leading-none">
                      {getFullName(auth.user?.first_name, auth.user?.last_name, 'Dev User')}
                    </p>
                    {auth.user?.email && (
                      <p className="text-xs leading-none text-muted-foreground">
                        {auth.user.email}
                      </p>
                    )}
                  </div>
                </DropdownMenuLabel>
                {activePeriod && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => navigate('/tracker/my-report')}>
                      <FileText className="mr-2 h-4 w-4" />
                      My Report
                    </DropdownMenuItem>
                  </>
                )}
                {canAdmin && !auth.isImpersonating && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => setImpersonateOpen(true)}>
                      <UserRoundCog className="mr-2 h-4 w-4" />
                      Impersonate User
                    </DropdownMenuItem>
                  </>
                )}
                {auth.isImpersonating && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={handleStopImpersonating}>
                      <UserX className="mr-2 h-4 w-4" />
                      Stop Impersonating
                    </DropdownMenuItem>
                  </>
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
        </header>
        <main className="flex-1 p-6">
          <div className="w-full">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
      {impersonateOpen && (
        <ImpersonateDialog open={impersonateOpen} onOpenChange={setImpersonateOpen} />
      )}
    </SidebarProvider>
  );
}
