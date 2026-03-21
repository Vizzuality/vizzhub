import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { MONTHS } from '@/shared/constants/dates';
import { useCreatePeriod } from '../hooks/useReportingPeriods';
import { SELECT_CLASS } from '../utils/constants';

const DEFAULT_BASE_RATE = '175.00';

export default function PeriodForm(): JSX.Element {
  const [open, setOpen] = useState(false);
  const now = new Date();
  const [month, setMonth] = useState(String(now.getMonth() + 1));
  const [baseRate, setBaseRate] = useState(DEFAULT_BASE_RATE);
  const [error, setError] = useState<string | null>(null);
  const createPeriod = useCreatePeriod();

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);
    const date = `${now.getFullYear()}-${month.padStart(2, '0')}-01`;
    const parsed = Number.parseFloat(baseRate);
    createPeriod.mutate(
      { date, base_rate: Number.isNaN(parsed) ? undefined : parsed },
      {
        onSuccess: () => {
          setOpen(false);
          setBaseRate(DEFAULT_BASE_RATE);
        },
        onError: (err: unknown) => {
          const detail = (err as { response?: { data?: { detail?: string } } })
            ?.response?.data?.detail;
          setError(detail ?? 'A period for this month already exists.');
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New Period</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Reporting Period</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="period-month">Month ({now.getFullYear()})</Label>
            <select
              id="period-month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className={`${SELECT_CLASS} h-9 w-full`}
            >
              {MONTHS.map((name, i) => (
                <option key={i + 1} value={String(i + 1)}>{name}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="period-base-rate">Base Rate</Label>
            <Input
              id="period-base-rate"
              type="number"
              step="0.01"
              min="0"
              value={baseRate}
              onChange={(e) => setBaseRate(e.target.value)}
            />
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createPeriod.isPending}>
              {createPeriod.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
