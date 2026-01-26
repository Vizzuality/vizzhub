import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface ProjectDialogsProps {
  projectName: string;
  showDeleteConfirm: boolean;
  onDeleteConfirmChange: (open: boolean) => void;
  onConfirmDelete: () => void;
  showFinishDialog: boolean;
  onFinishDialogChange: (open: boolean) => void;
  onConfirmFinish: () => Promise<unknown>;
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
              onClick={onConfirmDelete}
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
              <div className="space-y-2">
                <p>When you mark this project as finished:</p>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>Jira and GitHub collectors will be disabled</li>
                  <li>Regular metric updates will be blocked</li>
                  <li>Client Satisfaction Survey will become editable</li>
                  <li>You can reopen the project later if needed</li>
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={async () => {
                await onConfirmFinish();
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
