import { useState } from 'react';
import { useCreateSnapshot, useProjectSnapshots } from '../../hooks/useSnapshots';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Calendar, Plus, Loader2 } from 'lucide-react';

interface SnapshotManagerProps {
  projectId: string;
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function getYearOptions(): number[] {
  const currentYear = new Date().getFullYear();
  return [currentYear - 1, currentYear, currentYear + 1];
}

export default function SnapshotManager({ projectId }: SnapshotManagerProps): JSX.Element {
  const currentDate = new Date();
  const [year, setYear] = useState(currentDate.getFullYear());
  const [month, setMonth] = useState(currentDate.getMonth() + 1);

  const createSnapshot = useCreateSnapshot(projectId);
  const { data: snapshots } = useProjectSnapshots(projectId);

  const handleCreate = () => {
    createSnapshot.mutate({ period_year: year, period_month: month });
  };

  const existingPeriods = new Set(
    snapshots?.map((s) => `${s.period_year}-${s.period_month}`) ?? []
  );
  const periodExists = existingPeriods.has(`${year}-${month}`);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Create Snapshot
        </CardTitle>
        <CardDescription>
          Create a monthly snapshot to track historical scores.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex flex-col gap-2">
            <label htmlFor="year-select" className="text-sm font-medium">
              Year
            </label>
            <select
              id="year-select"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {getYearOptions().map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="month-select" className="text-sm font-medium">
              Month
            </label>
            <select
              id="month-select"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {MONTHS.map((m, idx) => (
                <option key={idx + 1} value={idx + 1}>{m}</option>
              ))}
            </select>
          </div>

          <Button
            onClick={handleCreate}
            disabled={createSnapshot.isPending || periodExists}
          >
            {createSnapshot.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Create Snapshot
              </>
            )}
          </Button>
        </div>

        {periodExists && (
          <p className="text-sm text-muted-foreground mt-2">
            A snapshot for {MONTHS[month - 1]} {year} already exists.
          </p>
        )}

        {createSnapshot.isError && (
          <p className="text-sm text-destructive mt-2">
            Failed to create snapshot. Make sure there are metrics for this period.
          </p>
        )}

        {createSnapshot.isSuccess && (
          <p className="text-sm text-green-600 mt-2">
            Snapshot created successfully.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
