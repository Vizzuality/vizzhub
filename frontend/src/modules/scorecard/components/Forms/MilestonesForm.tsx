import { useEffect } from 'react';
import { useForm, useFieldArray, useWatch } from 'react-hook-form';
import { Plus, Trash2, Calendar, Flag } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import type { Milestone } from '../../types';

interface MilestonesFormData {
  milestones: {
    name: string;
    planned_date: string;
    actual_date: string;
  }[];
}

interface MilestonesFormProps {
  initialData?: Milestone[];
  onSubmit: (data: Milestone[]) => void;
  onCancel: () => void;
  isLoading?: boolean;
  onDirtyChange?: (isDirty: boolean) => void;
  onValuesChange?: (data: Milestone[]) => void;
}

export default function MilestonesForm({
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
  onDirtyChange,
  onValuesChange,
}: MilestonesFormProps): JSX.Element {
  const {
    register,
    control,
    handleSubmit,
    getValues,
    formState: { errors, isDirty },
  } = useForm<MilestonesFormData>({
    defaultValues: {
      milestones: initialData?.map((m) => ({
        name: m.name,
        planned_date: m.planned_date,
        actual_date: m.actual_date ?? '',
      })) ?? [{ name: '', planned_date: '', actual_date: '' }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'milestones',
  });

  const watchedMilestones = useWatch({
    control,
    name: 'milestones',
  });

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    if (onValuesChange) {
      const currentValues = getValues('milestones');
      if (currentValues) {
        const milestones: Milestone[] = currentValues
          .filter((m) => m.name && m.planned_date)
          .map((m) => ({
            name: m.name,
            planned_date: m.planned_date,
            actual_date: m.actual_date || undefined,
          }));
        onValuesChange(milestones);
      }
    }
  }, [watchedMilestones, fields, isDirty, getValues, onValuesChange]);

  const handleFormSubmit = (data: MilestonesFormData): void => {
    const milestones: Milestone[] = data.milestones
      .filter((m) => m.name && m.planned_date)
      .map((m) => ({
        name: m.name,
        planned_date: m.planned_date,
        actual_date: m.actual_date || undefined,
      }));
    onSubmit(milestones);
  };

  const addMilestone = (): void => {
    append({ name: '', planned_date: '', actual_date: '' });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
      <div className="space-y-3">
        {fields.map((field, index) => (
          <div
            key={field.id}
            className="grid grid-cols-[1fr_140px_140px_40px] gap-3 items-end p-3 bg-muted/50 rounded-lg"
          >
            <div className="space-y-1">
              {index === 0 && (
                <Label className="text-xs flex items-center gap-1">
                  <Flag className="w-3 h-3" />
                  Milestone Name
                </Label>
              )}
              <Input
                {...register(`milestones.${index}.name`, {
                  required: 'Name is required',
                })}
                placeholder="e.g., MVP Release"
              />
              {errors.milestones?.[index]?.name && (
                <p className="text-xs text-destructive">
                  {errors.milestones[index]?.name?.message}
                </p>
              )}
            </div>

            <div className="space-y-1">
              {index === 0 && (
                <Label className="text-xs flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Planned
                </Label>
              )}
              <Input
                type="date"
                {...register(`milestones.${index}.planned_date`, {
                  required: 'Date is required',
                })}
              />
              {errors.milestones?.[index]?.planned_date && (
                <p className="text-xs text-destructive">Required</p>
              )}
            </div>

            <div className="space-y-1">
              {index === 0 && (
                <Label className="text-xs flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Actual
                </Label>
              )}
              <Input
                type="date"
                {...register(`milestones.${index}.actual_date`)}
              />
            </div>

            <div className={index === 0 ? 'pt-5' : ''}>
              {fields.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => remove(index)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={addMilestone}
        className="w-full"
      >
        <Plus className="w-4 h-4 mr-2" />
        Add Milestone
      </Button>

      <div className="flex justify-end gap-2 pt-4">
        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          disabled={isLoading}
          className="border border-input"
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : 'Save Milestones'}
        </Button>
      </div>
    </form>
  );
}
