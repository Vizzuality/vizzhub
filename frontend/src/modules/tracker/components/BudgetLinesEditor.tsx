import { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { NativeSelect } from '@/shared/components/ui/native-select';
import { Card, CardContent } from '@/shared/components/ui/card';
import { useFunctionalAreas } from '../hooks/useBudgetLines';
import type { BudgetLine, BudgetLineCreate } from '../types/tracker';

const OTHER_VALUE = '__other__';

interface BudgetLineRow {
  selectValue: string;
  days: string;
  details: string;
}

function newRow(): BudgetLineRow {
  return { selectValue: '', days: '', details: '' };
}

interface BudgetLinesEditorProps {
  readonly initialData: BudgetLine[] | undefined;
  readonly onLinesChange: (lines: BudgetLineCreate[]) => void;
}

function toCreatePayload(rows: BudgetLineRow[]): BudgetLineCreate[] {
  return rows
    .filter((r) => r.days !== '' && Number(r.days) >= 0)
    .map((r) => ({
      functional_area_id: r.selectValue && r.selectValue !== OTHER_VALUE ? r.selectValue : null,
      days: Number(r.days),
      details: !r.selectValue || r.selectValue === OTHER_VALUE ? (r.details || 'Other costs') : null,
    }));
}

export default function BudgetLinesEditor({
  initialData,
  onLinesChange,
}: BudgetLinesEditorProps): JSX.Element {
  const { data: functionalAreas } = useFunctionalAreas();
  const [rows, setRows] = useState<BudgetLineRow[]>([newRow()]);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (initialized || !initialData) return;
    if (initialData.length > 0) {
      setRows(
        initialData.map((bl) => ({
          selectValue: bl.functional_area_id ?? (bl.details ? OTHER_VALUE : ''),
          days: bl.days?.toString() ?? '',
          details: bl.details ?? '',
        })),
      );
    }
    setInitialized(true);
  }, [initialData, initialized]);

  const updateRow = (index: number, field: keyof BudgetLineRow, value: string): void => {
    setRows((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      onLinesChange(toCreatePayload(next));
      return next;
    });
  };

  const addRow = (): void => {
    setRows((prev) => [...prev, newRow()]);
  };

  const removeRow = (index: number): void => {
    setRows((prev) => {
      const next = prev.filter((_, i) => i !== index);
      const result = next.length === 0 ? [newRow()] : next;
      onLinesChange(toCreatePayload(result));
      return result;
    });
  };

  const totalDays = rows.reduce((sum, r) => sum + (Number(r.days) || 0), 0);
  const usedAreaIds = new Set(
    rows.map((r) => r.selectValue).filter((v) => v && v !== OTHER_VALUE),
  );

  return (
    <section>
      <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">
        Budget Lines
      </h2>
      <Card>
        <CardContent className="pt-6 space-y-4">
          {/* Header */}
          <div className="grid grid-cols-[1fr_80px_50px_36px] sm:grid-cols-[1fr_100px_60px_36px] gap-2 sm:gap-3">
            <Label className="text-xs text-muted-foreground">Area</Label>
            <Label className="text-xs text-muted-foreground">Days</Label>
            <Label className="text-xs text-muted-foreground text-right">%</Label>
            <div />
          </div>

          {/* Rows */}
          <div className="space-y-3">
            {rows.map((row, index) => {
              const pct = totalDays > 0 && Number(row.days) > 0
                ? ((Number(row.days) / totalDays) * 100).toFixed(1)
                : '—';
              const isOther = row.selectValue === OTHER_VALUE;
              const showInlineText = isOther && row.details;

              return (
                <div key={index} className="space-y-2">
                  <div className="grid grid-cols-[1fr_80px_50px_36px] sm:grid-cols-[1fr_100px_60px_36px] gap-2 sm:gap-3 items-center">
                    {showInlineText ? (
                      <Input
                        value={row.details}
                        onChange={(e) => updateRow(index, 'details', e.target.value)}
                        placeholder="e.g., Other costs"
                      />
                    ) : (
                      <NativeSelect
                        value={row.selectValue}
                        onChange={(e) => updateRow(index, 'selectValue', e.target.value)}
                      >
                        <option value="">Select area...</option>
                        <option value={OTHER_VALUE}>Other (custom label)</option>
                        {functionalAreas?.map((fa) => (
                          <option
                            key={fa.id}
                            value={fa.id}
                            disabled={usedAreaIds.has(fa.id) && row.selectValue !== fa.id}
                          >
                            {fa.name}
                          </option>
                        ))}
                      </NativeSelect>
                    )}
                    <Input
                      type="number"
                      min="0"
                      step="0.1"
                      value={row.days}
                      onChange={(e) => updateRow(index, 'days', e.target.value)}
                      placeholder="0"
                    />
                    <div className="flex items-center h-9 text-sm text-muted-foreground tabular-nums justify-end">
                      {pct}{pct !== '—' && '%'}
                    </div>
                    <div>
                      {rows.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 text-muted-foreground hover:text-destructive"
                          onClick={() => removeRow(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                  {isOther && !showInlineText && (
                    <Input
                      value={row.details}
                      onChange={(e) => updateRow(index, 'details', e.target.value)}
                      placeholder="e.g., Other costs, Flexible time"
                      className="text-sm"
                    />
                  )}
                </div>
              );
            })}
          </div>

          {totalDays > 0 && (
            <div className="flex justify-between items-center pt-3 border-t text-sm">
              <span className="font-medium text-muted-foreground">Total</span>
              <span className="font-medium tabular-nums">{totalDays} days</span>
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addRow}
            className="w-full"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Budget Line
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
