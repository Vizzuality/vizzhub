import { useState, type ReactNode, type Dispatch, type SetStateAction } from 'react';
import { Pencil, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface EditableMetricCardProps<T> {
  title: string;
  description: string;
  tooltipContent: ReactNode;
  indicatorValue?: number | null;
  target?: number;
  data: T | null | undefined;
  onSave: (data: T) => Promise<unknown>;
  isPending: boolean;
  renderEditForm: (form: T, setForm: Dispatch<SetStateAction<T>>) => ReactNode;
  renderDisplay: (data: T | null | undefined, indicatorValue: number | null | undefined, target: number | undefined) => ReactNode;
  defaultFormState: T;
  editButtonLabel?: string;
  disabled?: boolean;
  disabledContent?: ReactNode;
}

export default function EditableMetricCard<T>({
  title,
  description,
  tooltipContent,
  indicatorValue,
  target,
  data,
  onSave,
  isPending,
  renderEditForm,
  renderDisplay,
  defaultFormState,
  editButtonLabel,
  disabled = false,
  disabledContent,
}: EditableMetricCardProps<T>): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<T>(defaultFormState);

  const handleStartEdit = (): void => {
    setForm(data ?? defaultFormState);
    setIsEditing(true);
  };

  const handleSave = async (): Promise<void> => {
    await onSave(form);
    setIsEditing(false);
  };

  const handleCancel = (): void => {
    setIsEditing(false);
    setForm(data ?? defaultFormState);
  };

  const hasData = data !== null && data !== undefined;
  const buttonLabel = editButtonLabel ?? (hasData ? 'Edit' : 'Add');

  return (
    <Card className={cn(disabled && 'opacity-60')}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{title}</CardTitle>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-muted-foreground hover:text-foreground transition-colors">
                  <Info className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">{tooltipContent}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {disabled && disabledContent ? (
          disabledContent
        ) : (
          <>
            <div className="p-4 bg-muted/50 rounded-lg border space-y-3">
              {isEditing ? (
                <div className="space-y-4">
                  {renderEditForm(form, setForm)}
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" onClick={handleSave} disabled={isPending}>
                      {isPending ? 'Saving...' : 'Save'}
                    </Button>
                    <Button size="sm" variant="outline" onClick={handleCancel}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                renderDisplay(data, indicatorValue, target)
              )}
            </div>
            {!isEditing && (
              <Button variant="outline" size="sm" className="w-full" onClick={handleStartEdit}>
                <Pencil className="w-4 h-4 mr-2" />
                {buttonLabel}
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
