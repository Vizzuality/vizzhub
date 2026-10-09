import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { ALL_SENTINEL, ATTENDING_LABELS } from '../utils/constants';

interface AttendingFilterSelectProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export function AttendingFilterSelect({
  value,
  onChange,
}: AttendingFilterSelectProps): JSX.Element {
  return (
    <Select
      value={value || ALL_SENTINEL}
      onValueChange={(v) => onChange(v === ALL_SENTINEL ? '' : v)}
    >
      <SelectTrigger className="w-[140px] h-9 text-sm">
        <SelectValue placeholder="Attending" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_SENTINEL}>All Attending</SelectItem>
        <SelectItem value="yes">{ATTENDING_LABELS.yes}</SelectItem>
        <SelectItem value="maybe">{ATTENDING_LABELS.maybe}</SelectItem>
        <SelectItem value="no">{ATTENDING_LABELS.no}</SelectItem>
        <SelectItem value="attended">Attended</SelectItem>
      </SelectContent>
    </Select>
  );
}
