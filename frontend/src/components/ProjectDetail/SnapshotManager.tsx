import { useState } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FileDown, ChevronDown, ChevronRight } from 'lucide-react';
import HistoricalCaptureSection from './HistoricalCaptureSection';

interface SnapshotManagerProps {
  readonly projectId: string;
}

export default function SnapshotManager({
  projectId,
}: SnapshotManagerProps): JSX.Element {
  const [isExportExpanded, setIsExportExpanded] = useState(false);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <HistoricalCaptureSection projectId={projectId} />

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
              Export project data and reports
            </CardDescription>
          )}
        </CardHeader>
        {isExportExpanded && (
          <CardContent>
            <Button variant="outline" disabled>
              <FileDown className="mr-2 h-4 w-4" />
              Export to CSV
            </Button>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
