import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';

interface MonthRangePickerProps {
  readonly startDate: string;
  readonly endDate: string;
  readonly onChange: (start: string, end: string) => void;
  readonly idPrefix?: string;
}

export function MonthRangePicker({
  startDate,
  endDate,
  onChange,
  idPrefix = '',
}: MonthRangePickerProps): JSX.Element {
  const startId = `${idPrefix}start-month`;
  const endId = `${idPrefix}end-month`;

  return (
    <div className="flex items-end gap-4">
      <div className="space-y-1">
        <Label htmlFor={startId}>From</Label>
        <Input
          id={startId}
          type="month"
          value={startDate}
          onChange={(e) => onChange(e.target.value, endDate)}
          className="w-40"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={endId}>To</Label>
        <Input
          id={endId}
          type="month"
          value={endDate}
          onChange={(e) => onChange(startDate, e.target.value)}
          className="w-40"
        />
      </div>
    </div>
  );
}
