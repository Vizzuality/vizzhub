import { Github, Package, Puzzle } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import type { InstallMethod } from '../types/devstack';

interface InstallMethodBadgeProps {
  readonly method: InstallMethod;
  readonly iconSize?: number;
}

function renderIcon(method: InstallMethod, iconSize: number): JSX.Element {
  if (method === 'github') return <Github size={iconSize} />;
  if (method === 'npm') return <Package size={iconSize} />;
  return <Puzzle size={iconSize} />;
}

function renderLabel(method: InstallMethod): string {
  if (method === 'claude_plugin') return 'plugin';
  return method;
}

export function InstallMethodBadge({ method, iconSize = 10 }: InstallMethodBadgeProps): JSX.Element {
  return (
    <Badge variant="outline" className="text-xs flex items-center gap-1">
      {renderIcon(method, iconSize)}
      {renderLabel(method)}
    </Badge>
  );
}
