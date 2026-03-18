import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import type { ReportPart } from '../types/tracker';
import { useUpdateReportPart, useDeleteReportPart } from '../hooks/useReports';

interface ReportPartRowProps {
  part: ReportPart;
  reportId: string;
}

export default function ReportPartRow({
  part,
  reportId,
}: ReportPartRowProps): JSX.Element {
  const [percentage, setPercentage] = useState(
    part.percentage !== null ? (part.percentage * 100).toFixed(1) : '',
  );
  const updatePart = useUpdateReportPart(reportId);
  const deletePart = useDeleteReportPart(reportId);

  const handleBlur = (): void => {
    const newPct = parseFloat(percentage) / 100;
    if (isNaN(newPct) || newPct === part.percentage) return;
    updatePart.mutate({ id: part.id, data: { percentage: newPct } });
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  return (
    <tr className="border-b">
      <td className="py-2 px-3 text-sm">
        {part.project_name || part.project_id.slice(0, 8)}
      </td>
      <td className="py-2 px-3">
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
      <td className="py-2 px-3 text-right text-sm">
        {part.days !== null ? part.days.toFixed(2) : '-'}
      </td>
      <td className="py-2 px-3">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => deletePart.mutate(part.id)}
        >
          <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
        </Button>
      </td>
    </tr>
  );
}
