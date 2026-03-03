import { useState, useMemo } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { MONTH_NAMES } from '../../utils/dateUtils';

interface ProjectDialogsProps {
  projectName: string;
  showDeleteConfirm: boolean;
  onDeleteConfirmChange: (open: boolean) => void;
  onConfirmDelete: () => Promise<void>;
  showFinishDialog: boolean;
  onFinishDialogChange: (open: boolean) => void;
  onConfirmFinish: (finishedAt: string) => Promise<unknown>;
}

export default function ProjectDialogs({
  projectName,
  showDeleteConfirm,
  onDeleteConfirmChange,
  onConfirmDelete,
  showFinishDialog,
  onFinishDialogChange,
  onConfirmFinish,
}: ProjectDialogsProps): JSX.Element {
  const now = new Date();
  const [finishMonth, setFinishMonth] = useState(now.getMonth() + 1);
  const [finishYear, setFinishYear] = useState(now.getFullYear());

  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    return Array.from({ length: 5 }, (_, i) => currentYear - i + 1);
  }, []);

  const getFinishedAtDate = (): string => {
    const lastDay = new Date(finishYear, finishMonth, 0).getDate();
    return `${finishYear}-${String(finishMonth).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  };

  return (
    <>
      <AlertDialog open={showDeleteConfirm} onOpenChange={onDeleteConfirmChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Project?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the project "
              {projectName}" and all associated metrics.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={async (e) => {
                e.preventDefault();
                await onConfirmDelete();
                onDeleteConfirmChange(false);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showFinishDialog} onOpenChange={onFinishDialogChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Mark Project as Finished?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>Select the month when this project finished:</p>
                <div className="flex gap-2">
                  <Select
                    value={String(finishMonth)}
                    onValueChange={(v) => setFinishMonth(Number(v))}
                  >
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MONTH_NAMES.map((name, idx) => (
                        <SelectItem key={name} value={String(idx + 1)}>
                          {name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={String(finishYear)}
                    onValueChange={(v) => setFinishYear(Number(v))}
                  >
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {yearOptions.map((year) => (
                        <SelectItem key={year} value={String(year)}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2 text-sm text-muted-foreground">
                  <p>When you mark this project as finished:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Timeline will stop at the selected month</li>
                    <li>Jira and GitHub collectors will be disabled</li>
                    <li>Client Satisfaction Survey will become editable</li>
                    <li>You can reopen the project later if needed</li>
                  </ul>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={async () => {
                await onConfirmFinish(getFinishedAtDate());
                onFinishDialogChange(false);
              }}
              className="bg-score-green hover:bg-score-green/80 text-white dark:text-black"
            >
              Mark as Finished
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
