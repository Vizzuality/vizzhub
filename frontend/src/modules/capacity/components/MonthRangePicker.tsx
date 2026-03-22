import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';

interface MonthRangePickerProps {
  readonly startDate: string;
  readonly endDate: string;
  readonly onChange: (start: string, end: string) => void;
}

export function MonthRangePicker({
  startDate,
  endDate,
  onChange,
}: MonthRangePickerProps): JSX.Element {
  return (
    <div className="flex items-end gap-4">
      <div className="space-y-1">
        <Label htmlFor="start-month">From</Label>
        <Input
          id="start-month"
          type="month"
          value={startDate}
          onChange={(e) => onChange(e.target.value, endDate)}
          className="w-40"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="end-month">To</Label>
        <Input
          id="end-month"
          type="month"
          value={endDate}
          onChange={(e) => onChange(startDate, e.target.value)}
          className="w-40"
        />
      </div>
    </div>
  );
}
