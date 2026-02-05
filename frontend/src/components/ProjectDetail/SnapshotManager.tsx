import { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MonthYearPicker } from '@/components/ui/month-year-picker';
import { NativeSelect } from '@/components/ui/native-select';
import { FileDown, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import HistoricalCaptureSection from './HistoricalCaptureSection';
import { useExport } from '../../hooks/useExport';
import { useAuth } from '@/hooks/useAuth';

interface SnapshotManagerProps {
  readonly projectId: string;
  readonly projectName: string;
}

export default function SnapshotManager({
  projectId,
  projectName,
}: SnapshotManagerProps): JSX.Element {
  const currentDate = new Date();
  const [isExportExpanded, setIsExportExpanded] = useState(false);

  const [fromYear, setFromYear] = useState(currentDate.getFullYear());
  const [fromMonth, setFromMonth] = useState(1);
  const [toYear, setToYear] = useState(currentDate.getFullYear());
  const [toMonth, setToMonth] = useState(currentDate.getMonth() + 1);
  const [snapshotType, setSnapshotType] = useState('cumulative');

  const { exportProject, isExporting, error } = useExport();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const handleExport = async (): Promise<void> => {
    await exportProject(
      projectId,
      projectName,
      fromYear,
      fromMonth,
      toYear,
      toMonth,
      snapshotType,
    );
  };

  const monthCount = (toYear - fromYear) * 12 + (toMonth - fromMonth) + 1;

  return (
    <div className={`grid grid-cols-1 ${isAdmin ? 'md:grid-cols-2' : ''} gap-4`}>
      {isAdmin && <HistoricalCaptureSection projectId={projectId} />}

      <Card>
        <CardHeader
          className="cursor-pointer select-none"
          onClick={() => setIsExportExpanded(!isExportExpanded)}
        >
          <CardTitle className="flex items-center gap-2">
            {isExportExpanded ? (
              <ChevronDown className="h-5 w-5" />
            ) : (
              <ChevronRight className="h-5 w-5" />
            )}
            <FileDown className="h-5 w-5" />
            Export
          </CardTitle>
          {isExportExpanded && (
            <CardDescription>
              Export project scorecard to XLSX
            </CardDescription>
          )}
        </CardHeader>
        {isExportExpanded && (
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-muted-foreground">From</span>
              <MonthYearPicker
                month={fromMonth}
                year={fromYear}
                onMonthChange={setFromMonth}
                onYearChange={setFromYear}
                disabled={isExporting}
              />
              <span className="text-sm text-muted-foreground">to</span>
              <MonthYearPicker
                month={toMonth}
                year={toYear}
                onMonthChange={setToMonth}
                onYearChange={setToYear}
                disabled={isExporting}
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Snapshot</span>
              <NativeSelect
                value={snapshotType}
                onChange={(e) => setSnapshotType(e.target.value)}
                disabled={isExporting}
              >
                <option value="cumulative">Cumulative</option>
                <option value="punctual">Punctual</option>
              </NativeSelect>
            </div>

            {monthCount > 0 && (
              <p className="text-sm text-muted-foreground">
                {monthCount} month{monthCount > 1 ? 's' : ''} of data.
              </p>
            )}

            <Button
              onClick={handleExport}
              disabled={isExporting || monthCount <= 0}
            >
              {isExporting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <FileDown className="mr-2 h-4 w-4" />
                  Export XLSX
                </>
              )}
            </Button>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                {error}
              </div>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );
}
