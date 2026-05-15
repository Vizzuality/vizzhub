import { useState } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Check, Pencil, Plus, Trash2 } from 'lucide-react';
import {
  useNonStaffCosts,
  useCreateNonStaffCost,
  useUpdateNonStaffCost,
  useDeleteNonStaffCost,
} from '../hooks/useNonStaffCosts';
import { formatCurrency, formatPeriodDate } from '../utils/constants';
import type { NonStaffCost, NonStaffCostType, PeriodCostBreakdown } from '../types/tracker';

const COST_TYPES: NonStaffCostType[] = ['outsource', 'travel', 'servers', 'others'];

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface NonStaffCostsCardProps {
  readonly projectId: string;
  readonly periods: PeriodCostBreakdown[];
}

function CostRowActions({
  cost,
  projectId,
  periods,
}: {
  readonly cost: NonStaffCost;
  readonly projectId: string;
  readonly periods: PeriodCostBreakdown[];
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [editCostType, setEditCostType] = useState<NonStaffCostType>(
    cost.cost_type as NonStaffCostType,
  );
  const [editAmount, setEditAmount] = useState(cost.cost.toString());
  const [editDetails, setEditDetails] = useState(cost.details ?? '');
  const updateMutation = useUpdateNonStaffCost(projectId);
  const deleteMutation = useDeleteNonStaffCost(projectId);

  const periodLabel = periods.find((p) => p.period_id === cost.reporting_period_id);

  const handleSave = (): void => {
    const amount = Number.parseFloat(editAmount);
    if (Number.isNaN(amount) || amount <= 0) return;
    updateMutation.mutate(
      {
        costId: cost.id,
        data: {
          cost: amount,
          cost_type: editCostType,
          details: editDetails || null,
        },
      },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (editing) {
    return (
      <tr className="border-b last:border-0">
        <td className="py-2 text-sm">
          {periodLabel ? formatPeriodDate(periodLabel.date) : '\u2014'}
        </td>
        <td className="py-2">
          <select
            className="h-7 rounded border bg-background px-2 text-sm"
            value={editCostType}
            onChange={(e) => setEditCostType(e.target.value as NonStaffCostType)}
          >
            {COST_TYPES.map((t) => (
              <option key={t} value={t}>{capitalize(t)}</option>
            ))}
          </select>
        </td>
        <td className="py-2">
          <Input
            value={editDetails}
            onChange={(e) => setEditDetails(e.target.value)}
            placeholder="Details"
            className="h-7 text-sm px-1"
          />
        </td>
        <td className="py-2">
          <Input
            type="number"
            min="0"
            step="0.01"
            value={editAmount}
            onChange={(e) => setEditAmount(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            className="w-24 h-7 text-right text-sm px-1"
            autoFocus
          />
        </td>
        <td className="py-2 text-right">
          <div className="flex items-center gap-1 justify-end">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleSave}
              disabled={updateMutation.isPending}
            >
              <Check className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="group/row border-b last:border-0">
      <td className="py-2 text-sm">
        {periodLabel ? formatPeriodDate(periodLabel.date) : '\u2014'}
      </td>
      <td className="py-2 text-sm">{capitalize(cost.cost_type)}</td>
      <td className="py-2 text-sm text-muted-foreground">{cost.details ?? '\u2014'}</td>
      <td className="py-2 text-sm text-right tabular-nums">{formatCurrency(cost.cost)}</td>
      <td className="py-2 text-right">
        <div className="flex items-center gap-1 justify-end">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-50 hover:opacity-100"
            onClick={() => {
              setEditCostType(cost.cost_type as NonStaffCostType);
              setEditAmount(cost.cost.toString());
              setEditDetails(cost.details ?? '');
              setEditing(true);
            }}
          >
            <Pencil className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-50 hover:opacity-100 text-destructive"
            onClick={() => deleteMutation.mutate(cost.id)}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </td>
    </tr>
  );
}

export default function NonStaffCostsCard({
  projectId,
  periods,
}: NonStaffCostsCardProps): JSX.Element {
  const { data: costs } = useNonStaffCosts(projectId);
  const createMutation = useCreateNonStaffCost(projectId);
  const [adding, setAdding] = useState(false);
  const [newPeriodId, setNewPeriodId] = useState('');
  const [newCostType, setNewCostType] = useState<NonStaffCostType>('outsource');
  const [newAmount, setNewAmount] = useState('');
  const [newDetails, setNewDetails] = useState('');

  const totalCost = (costs ?? []).reduce((s, c) => s + Number(c.cost ?? 0), 0);

  const handleAdd = (): void => {
    const amount = Number.parseFloat(newAmount);
    if (!newPeriodId || Number.isNaN(amount) || amount <= 0) return;
    createMutation.mutate(
      {
        project_id: projectId,
        reporting_period_id: newPeriodId,
        cost: amount,
        cost_type: newCostType,
        details: newDetails || null,
      },
      {
        onSuccess: () => {
          setAdding(false);
          setNewPeriodId('');
          setNewCostType('outsource');
          setNewAmount('');
          setNewDetails('');
        },
      },
    );
  };

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Non-staff Costs
          </div>
          {costs && costs.length > 0 && (
            <div className="text-sm tabular-nums text-muted-foreground">
              {formatCurrency(totalCost)}
            </div>
          )}
        </div>

        {costs && costs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="text-left font-medium pb-1">Period</th>
                  <th className="text-left font-medium pb-1">Type</th>
                  <th className="text-left font-medium pb-1">Details</th>
                  <th className="text-right font-medium pb-1">Cost</th>
                  <th className="w-20" />
                </tr>
              </thead>
              <tbody>
                {costs.map((c) => (
                  <CostRowActions
                    key={c.id}
                    cost={c}
                    projectId={projectId}
                    periods={periods}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {costs?.length === 0 && !adding && (
          <p className="text-muted-foreground text-sm">No non-staff costs</p>
        )}

        {adding ? (
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <select
              className="h-8 rounded border bg-background px-2 text-sm flex-1 min-w-[120px]"
              value={newPeriodId}
              onChange={(e) => setNewPeriodId(e.target.value)}
            >
              <option value="">Select period</option>
              {periods.map((p) => (
                <option key={p.period_id} value={p.period_id}>
                  {formatPeriodDate(p.date)}
                </option>
              ))}
            </select>
            <select
              className="h-8 rounded border bg-background px-2 text-sm"
              value={newCostType}
              onChange={(e) => setNewCostType(e.target.value as NonStaffCostType)}
            >
              {COST_TYPES.map((t) => (
                <option key={t} value={t}>{capitalize(t)}</option>
              ))}
            </select>
            <Input
              type="number"
              min="0"
              step="0.01"
              placeholder="Amount"
              value={newAmount}
              onChange={(e) => setNewAmount(e.target.value)}
              className="w-28 h-8 text-right text-sm"
            />
            <Input
              placeholder="Details"
              value={newDetails}
              onChange={(e) => setNewDetails(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              className="h-8 text-sm min-w-[120px] flex-1"
            />
            <Button
              size="sm"
              className="h-8"
              onClick={handleAdd}
              disabled={createMutation.isPending}
            >
              Save
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => setAdding(false)}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="mt-3 gap-1 text-muted-foreground"
            onClick={() => setAdding(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            Add cost
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
