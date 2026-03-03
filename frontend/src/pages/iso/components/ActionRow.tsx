import { Badge } from '@/shared/components/ui/badge';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import type { AccessReviewAction } from '@/types';
import {
  formatChangeDetails,
  getChangeTypeBadgeClasses,
  formatChangeType,
} from './helpers';

type ActionTaken = NonNullable<AccessReviewAction['action_taken']>;

export const ACTION_OPTIONS: { value: ActionTaken; label: string }[] = [
  { value: 'accepted', label: 'Accepted' },
  { value: 'removed', label: 'Removed' },
  { value: 'corrected', label: 'Corrected' },
  { value: 'exception', label: 'Exception' },
];

export interface ActionState {
  actionTaken: string;
  justification: string;
  exceptionUntil: string;
}

interface ActionRowProps {
  readonly action: AccessReviewAction;
  readonly state: ActionState;
  readonly isSigned: boolean;
  readonly onChange: (state: ActionState) => void;
}

export default function ActionRow({ action, state, isSigned, onChange }: ActionRowProps): JSX.Element {
  return (
    <tr className="border-b last:border-b-0">
      <td className="py-3 pr-4 text-sm">
        <div>
          {action.subject_label || action.subject_id}
          <span className="ml-1 text-muted-foreground">
            ({action.subject_type})
          </span>
        </div>
      </td>
      <td className="py-3 pr-4">
        <Badge variant="outline" className={getChangeTypeBadgeClasses(action.change_type)}>
          {formatChangeType(action.change_type)}
        </Badge>
      </td>
      <td className="py-3 pr-4 text-sm max-w-xs truncate">
        {formatChangeDetails(action.previous_value, action.current_value)}
      </td>
      <td className="py-3 pr-4">
        {isSigned ? (
          <span className="text-sm">{action.action_taken ?? '\u2014'}</span>
        ) : (
          <Select
            value={state.actionTaken || 'none'}
            onValueChange={(v) =>
              onChange({ ...state, actionTaken: v === 'none' ? '' : v })
            }
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Select...</SelectItem>
              {ACTION_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </td>
      <td className="py-3 pr-4">
        {isSigned ? (
          <span className="text-sm">{action.justification ?? '\u2014'}</span>
        ) : (
          <div className="space-y-2">
            <Textarea
              value={state.justification}
              onChange={(e) =>
                onChange({ ...state, justification: e.target.value })
              }
              placeholder="Justification..."
              className="w-48 min-h-[60px]"
              rows={2}
            />
            {state.actionTaken === 'exception' && (
              <input
                type="date"
                value={state.exceptionUntil}
                onChange={(e) =>
                  onChange({ ...state, exceptionUntil: e.target.value })
                }
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              />
            )}
          </div>
        )}
      </td>
    </tr>
  );
}
