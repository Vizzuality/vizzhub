import { Github, Package } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import type { InstallMethod } from '../types/devstack';

interface InstallMethodBadgeProps {
  readonly method: InstallMethod;
  readonly iconSize?: number;
}

export function InstallMethodBadge({ method, iconSize = 10 }: InstallMethodBadgeProps): JSX.Element {
  return (
    <Badge variant="outline" className="text-xs flex items-center gap-1">
      {method === 'github' ? <Github size={iconSize} /> : <Package size={iconSize} />}
      {method}
    </Badge>
  );
}
