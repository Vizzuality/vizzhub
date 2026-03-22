import type { ReactNode } from 'react';
import { usePermission } from './usePermission';
import type { Permission } from './constants';

interface CanProps {
  readonly do: Permission;
  readonly children: ReactNode;
}

export function Can({ do: permission, children }: CanProps): JSX.Element | null {
  const allowed = usePermission(permission);
  return allowed ? <>{children}</> : null;
}
