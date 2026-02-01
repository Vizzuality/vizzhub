import { MONTHS } from '@/constants/dates';
import { getYearOptions } from '@/utils/dateUtils';
import { NativeSelect } from './native-select';

interface MonthYearPickerProps {
  month: number;
  year: number;
  onMonthChange: (month: number) => void;
  onYearChange: (year: number) => void;
  disabled?: boolean;
  showLabels?: boolean;
  monthLabel?: string;
  yearLabel?: string;
}

export function MonthYearPicker({
  month,
  year,
  onMonthChange,
  onYearChange,
  disabled = false,
  showLabels = false,
  monthLabel = 'Month',
  yearLabel = 'Year',
}: MonthYearPickerProps): JSX.Element {
  const years = getYearOptions();

  if (showLabels) {
    return (
      <>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">{yearLabel}</label>
          <NativeSelect
            value={year}
            onChange={(e) => onYearChange(Number(e.target.value))}
            disabled={disabled}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">{monthLabel}</label>
          <NativeSelect
            value={month}
            onChange={(e) => onMonthChange(Number(e.target.value))}
            disabled={disabled}
          >
            {MONTHS.map((m, idx) => (
              <option key={idx + 1} value={idx + 1}>
                {m}
              </option>
            ))}
          </NativeSelect>
        </div>
      </>
    );
  }

  return (
    <>
      <NativeSelect
        value={month}
        onChange={(e) => onMonthChange(Number(e.target.value))}
        disabled={disabled}
      >
        {MONTHS.map((m, idx) => (
          <option key={idx + 1} value={idx + 1}>
            {m}
          </option>
        ))}
      </NativeSelect>
      <NativeSelect
        value={year}
        onChange={(e) => onYearChange(Number(e.target.value))}
        disabled={disabled}
      >
        {years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </NativeSelect>
    </>
  );
}
