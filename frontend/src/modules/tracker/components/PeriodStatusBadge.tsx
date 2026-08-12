import { Badge } from '@/shared/components/ui/badge';
import { PERIOD_STATUS_COLORS } from '../utils/constants';
import type { ReportingPeriod } from '../types/tracker';

interface PeriodStatusBadgeProps {
  status: ReportingPeriod['status'];
}

export default function PeriodStatusBadge({
  status,
}: Readonly<PeriodStatusBadgeProps>): JSX.Element {
  return (
    <Badge variant="outline" className={PERIOD_STATUS_COLORS[status]}>
      {status}
    </Badge>
  );
}
