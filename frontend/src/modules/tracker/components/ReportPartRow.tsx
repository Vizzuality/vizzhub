import { useEffect, useState } from 'react';
import { ArrowRight, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import type { ReportPart } from '../types/tracker';
import { useUpdateReportPart, useDeleteReportPart } from '../hooks/useReports';

interface ReportPartRowProps {
  readonly part: ReportPart;
  readonly reportId: string;
  readonly suggestedPercentage?: number;
}

const GREEN_STYLE = { color: 'var(--accent-green)' };

export default function ReportPartRow({
  part,
  reportId,
  suggestedPercentage,
}: ReportPartRowProps): JSX.Element {
  const [percentage, setPercentage] = useState(
    part.percentage !== null ? (part.percentage * 100).toFixed(1) : '',
  );

  useEffect(() => {
    setPercentage(part.percentage !== null ? (part.percentage * 100).toFixed(1) : '');
  }, [part.percentage]);

  const updatePart = useUpdateReportPart(reportId);
  const deletePart = useDeleteReportPart(reportId);

  const handleBlur = (): void => {
    const newPct = Number.parseFloat(percentage) / 100;
    if (Number.isNaN(newPct) || newPct === part.percentage) return;
    updatePart.mutate({ id: part.id, data: { percentage: newPct } });
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  const handleApplySuggestion = (): void => {
    if (suggestedPercentage === undefined) return;
    const displayVal = suggestedPercentage.toFixed(1);
    setPercentage(displayVal);
    updatePart.mutate({ id: part.id, data: { percentage: suggestedPercentage / 100 } });
  };

  return (
    <tr className="border-b">
      <td className="py-1 px-2 text-sm max-w-[200px] truncate">
        {part.project_name || part.project_id.slice(0, 8)}
      </td>
      <td className="py-1 px-2 text-right">
        {suggestedPercentage !== undefined && (
          <button
            type="button"
            title="Apply planning suggestion"
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs font-medium whitespace-nowrap cursor-pointer opacity-80 hover:opacity-100 transition-opacity disabled:opacity-40 disabled:cursor-default"
            style={GREEN_STYLE}
            onClick={handleApplySuggestion}
            disabled={updatePart.isPending}
          >
            {suggestedPercentage.toFixed(1)}%
            <ArrowRight className="h-3 w-3" />
          </button>
        )}
      </td>
      <td className="py-1 px-2">
        <div className="flex items-center gap-1">
          <Input
            type="number"
            step="0.1"
            min="0"
            max="100"
            value={percentage}
            onChange={(e) => setPercentage(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            className="w-20 h-7 text-sm"
          />
          <span className="text-xs text-muted-foreground">%</span>
        </div>
      </td>
      <td className="py-1 px-2 text-right text-sm">
        {part.days !== null ? part.days.toFixed(2) : '-'}
      </td>
      <td className="py-1 px-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={() => deletePart.mutate(part.id)}
        >
          <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
        </Button>
      </td>
    </tr>
  );
}
