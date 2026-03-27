import { useAllocationUsers } from '@/modules/capacity/hooks/useAllocationUsers';
import { UserAllocationList } from '@/modules/capacity/components/UserAllocationList';

function formatPeriodsHeader(periods: string[]): string {
  if (periods.length === 0) return '';
  let lastYear = '';
  const parts: string[] = [];
  for (const p of periods) {
    const [year, month] = p.split('-');
    const date = new Date(Number(year), Number(month) - 1);
    const monthName = date.toLocaleDateString('en', { month: 'short' });
    if (year !== lastYear) {
      parts.push(`${monthName} ${year}`);
      lastYear = year;
    } else {
      parts.push(monthName);
    }
  }
  return `Based on ${parts.join(', ')}`;
}

export default function Allocation(): JSX.Element {
  const { data, isLoading, error } = useAllocationUsers();

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-semibold">Team Allocation</h1>
        {data && data.periods_used.length > 0 && (
          <span className="text-muted-foreground text-sm">
            {formatPeriodsHeader(data.periods_used)}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          Loading...
        </div>
      )}

      {error && (
        <div className="flex h-64 items-center justify-center text-destructive">
          Failed to load allocation data
        </div>
      )}

      {data && <UserAllocationList users={data.users} />}
    </div>
  );
}
