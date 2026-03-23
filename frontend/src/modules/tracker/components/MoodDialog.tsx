import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { Textarea } from '@/shared/components/ui/textarea';
import { useUpdateReport } from '../hooks/useReports';
import { useCreateAnonymousFeedback } from '../hooks/useMoods';
import { MOOD_ITEMS } from '../utils/constants';
import type { ReportUpdate } from '../types/tracker';

interface MoodDialogProps {
  open: boolean;
  onClose: () => void;
  reportId: string;
  periodId: string;
  periodMonth: number;
  periodYear: number;
}

export default function MoodDialog({
  open,
  onClose,
  reportId,
  periodId,
  periodMonth,
  periodYear,
}: MoodDialogProps): JSX.Element {
  const [selectedMood, setSelectedMood] = useState<number | null>(null);
  const [text, setText] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);

  const updateReport = useUpdateReport(reportId, periodId);
  const createAnonymousFeedback = useCreateAnonymousFeedback();

  const handleSubmit = async (): Promise<void> => {
    try {
      const reportUpdate: ReportUpdate = {};
      if (selectedMood !== null) {
        reportUpdate.mood = selectedMood;
      }
      if (text.trim() && !isAnonymous) {
        reportUpdate.feedback_text = text.trim();
      }

      if (Object.keys(reportUpdate).length > 0) {
        await updateReport.mutateAsync(reportUpdate);
      }

      if (text.trim() && isAnonymous) {
        await createAnonymousFeedback.mutateAsync({
          month: periodMonth,
          year: periodYear,
          text: text.trim(),
        });
      }
    } finally {
      onClose();
    }
  };

  const hasContent = selectedMood !== null || text.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>How did you feel during this period?</DialogTitle>
          <DialogDescription>Optional — helps us understand team wellbeing</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="flex gap-2 mb-1">
              {MOOD_ITEMS.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setSelectedMood(selectedMood === m.value ? null : m.value)}
                  title={m.label}
                  className={`text-2xl p-2 rounded-lg border-2 transition-all flex-1 ${
                    selectedMood === m.value
                      ? 'border-primary bg-primary/10'
                      : 'border-border opacity-60 hover:opacity-100'
                  }`}
                >
                  {m.emoji}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Your mood selection is linked to your report
            </p>
          </div>

          <div className="border-t" />

          <div>
            <Textarea
              placeholder="Want to share more? (optional)"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={2000}
              className="min-h-[72px] resize-y"
            />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="anonymous"
              checked={isAnonymous}
              onCheckedChange={(checked) => setIsAnonymous(checked === true)}
            />
            <label htmlFor="anonymous" className="text-sm text-muted-foreground cursor-pointer">
              Submit text anonymously
            </label>
            <span className="text-xs text-muted-foreground opacity-70">
              (only month/year stored, no link to you)
            </span>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onClose}>
            Skip
          </Button>
          <Button onClick={handleSubmit} disabled={!hasContent}>
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
