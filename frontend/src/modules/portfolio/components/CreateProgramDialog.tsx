import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { getApiErrorMessage } from '@/utils/apiErrors';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useCreateProgram } from '../hooks/usePrograms';

export function CreateProgramDialog(): JSX.Element {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const createProgram = useCreateProgram();

  const handleCreate = async (): Promise<void> => {
    setError('');
    try {
      const created = await createProgram.mutateAsync(name.trim());
      setOpen(false);
      navigate(`/admin/portfolio/programs/${created.id}`);
    } catch (err) {
      setError(
        getApiErrorMessage(err as Error, {
          conflict: 'A program with this name already exists',
          fallback: 'Could not create the program',
        }),
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); setName(''); setError(''); }}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Plus className="mr-1 h-3.5 w-3.5" />
          New program
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>New program</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="program-name">Name</Label>
          <Input
            id="program-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button
            onClick={() => void handleCreate()}
            disabled={!name.trim() || createProgram.isPending}
          >
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
