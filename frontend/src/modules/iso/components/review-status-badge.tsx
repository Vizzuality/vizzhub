import { Badge } from '@/shared/components/ui/badge';
import type { AccessReview } from '@/modules/iso/types/iso';

type ReviewStatus = AccessReview['status'];

const STATUS_CONFIG: Record<
  ReviewStatus,
  { variant: 'default' | 'secondary' | 'outline'; label: string }
> = {
  draft: { variant: 'secondary', label: 'Draft' },
  signed: { variant: 'default', label: 'Signed' },
};

export function ReviewStatusBadge({ status }: { readonly status: ReviewStatus }): JSX.Element {
  const { variant, label } = STATUS_CONFIG[status];
  return <Badge variant={variant}>{label}</Badge>;
}
