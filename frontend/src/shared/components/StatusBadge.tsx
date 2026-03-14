import { Badge } from '@/shared/components/ui/badge';
import { cn } from '@/lib/utils';
import { getStatusLabel } from '@/utils/projectStatus';

function getStatusBadgeClasses(status: string): string {
  switch (status) {
    case 'proposal':
      return 'bg-amber-100 text-amber-800 hover:bg-amber-100/80 dark:bg-amber-900 dark:text-amber-200';
    case 'finished':
      return 'bg-green-100 text-green-800 hover:bg-green-100/80 dark:bg-green-900 dark:text-green-200';
    default:
      return '';
  }
}

function getStatusVariant(status: string): 'default' | 'secondary' | 'outline' {
  switch (status) {
    case 'proposal': return 'outline';
    case 'live': return 'secondary';
    case 'finished': return 'default';
    default: return 'secondary';
  }
}

export function StatusBadge({ status }: { readonly status: string }): JSX.Element {
  return (
    <Badge
      variant={getStatusVariant(status)}
      className={cn('shrink-0', getStatusBadgeClasses(status))}
    >
      {getStatusLabel(status)}
    </Badge>
  );
}
