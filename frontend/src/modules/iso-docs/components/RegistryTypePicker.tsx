import { useState } from 'react';
import { Plus } from 'lucide-react';
import { AxiosError } from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { Button } from '@/shared/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { RegistryTypeDialog } from './RegistryTypeDialog';
import { useRegistryTypes, useCreateRegistryType } from '../hooks/useRegistryTypes';
import type { ColumnDef } from '../types/registry';

interface RegistryTypePickerProps {
  readonly value: string | null;
  readonly onChange: (typeId: string) => void;
}

export function RegistryTypePicker({ value, onChange }: RegistryTypePickerProps): JSX.Element {
  const { data: types = [] } = useRegistryTypes();
  const createType = useCreateRegistryType();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateType = (data: {
    name: string;
    description: string | null;
    is_yearly: boolean;
    schema: ColumnDef[];
  }): void => {
    setError(null);
    createType.mutate(data, {
      onSuccess: async (created) => {
        setDialogOpen(false);
        await queryClient.invalidateQueries({ queryKey: queryKeys.isoDocs.registryTypes });
        onChange(created.id);
      },
      onError: (err) => {
        if (err instanceof AxiosError) {
          const detail = err.response?.data?.detail;
          setError(typeof detail === 'string' ? detail : 'Failed to create registry type');
        } else {
          setError('Failed to create registry type');
        }
      },
    });
  };

  const handleOpenChange = (v: boolean): void => {
    if (!v) setError(null);
    setDialogOpen(v);
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Select value={value ?? ''} onValueChange={onChange}>
          <SelectTrigger className="flex-1">
            <SelectValue placeholder="Select registry type..." />
          </SelectTrigger>
          <SelectContent>
            {types.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => setDialogOpen(true)}
          title="Create new registry type"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      <RegistryTypeDialog
        open={dialogOpen}
        onOpenChange={handleOpenChange}
        onSave={handleCreateType}
        isSaving={createType.isPending}
        error={error}
      />
    </div>
  );
}
