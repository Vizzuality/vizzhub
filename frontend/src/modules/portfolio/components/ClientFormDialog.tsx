import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useCreateClient, useUpdateClient } from '../hooks/useClients';
import { getApiErrorDetail } from '@/utils/apiErrors';
import { CopperCompanyField } from './CopperCompanyField';
import type { Client, ClientCreate } from '../types/portfolio';

interface ClientFormDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly client: Client | null;
}

export function ClientFormDialog({ open, onOpenChange, client }: ClientFormDialogProps): JSX.Element {
  const create = useCreateClient();
  const update = useUpdateClient();
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [primaryContact, setPrimaryContact] = useState('');
  const [copperCompanyId, setCopperCompanyId] = useState<number | null>(null);
  const isEdit = client !== null;
  const saving = create.isPending || update.isPending;
  const saveError = create.error ?? update.error;
  const { reset: resetCreate } = create;
  const { reset: resetUpdate } = update;

  useEffect(() => {
    if (open) {
      setName(client?.name ?? '');
      setCode(client?.code ?? '');
      setPrimaryContact(client?.primary_contact ?? '');
      setCopperCompanyId(client?.copper_company_id ?? null);
      resetCreate();
      resetUpdate();
    }
  }, [open, client, resetCreate, resetUpdate]);

  const handleSave = async (): Promise<void> => {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      await save(trimmed);
    } catch {
      return; // shown below the form
    }
    onOpenChange(false);
  };

  const save = async (trimmed: string): Promise<void> => {
    if (isEdit && client) {
      await update.mutateAsync({
        id: client.id,
        data: {
          name: trimmed,
          code: code.trim() || null,
          primary_contact: primaryContact.trim() || null,
          ...(copperCompanyId === client.copper_company_id
            ? {}
            : { copper_company_id: copperCompanyId }),
        },
      });
    } else {
      const payload: ClientCreate = { name: trimmed };
      if (code.trim()) payload.code = code.trim();
      if (primaryContact.trim()) payload.primary_contact = primaryContact.trim();
      await create.mutateAsync(payload);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit client' : 'New client'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="client-name">Name</Label>
            <Input
              id="client-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Client name"
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="client-code">Code</Label>
            <Input
              id="client-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Optional client code"
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="client-primary-contact">Primary contact</Label>
            <Input
              id="client-primary-contact"
              value={primaryContact}
              onChange={(e) => setPrimaryContact(e.target.value)}
              placeholder="Optional primary contact"
              className="h-8 text-sm"
            />
          </div>
          {isEdit && client && open && (
            <CopperCompanyField
              value={copperCompanyId}
              onChange={setCopperCompanyId}
              clientName={client.name}
            />
          )}
          {saveError && (
            <p className="text-sm text-destructive">
              {getApiErrorDetail(saveError, 'Could not save the client.')}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || !name.trim()}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
