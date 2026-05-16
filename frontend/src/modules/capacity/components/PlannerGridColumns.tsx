import type { CellContext, HeaderContext } from '@tanstack/react-table';
import { AlertTriangle, ArrowLeftFromLine, ArrowRightFromLine, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';

export interface FlatRow {
  _type: 'header' | 'data' | 'add';
  groupId: string;
  groupName: string;
  hasWarning?: boolean;
  user_id?: string;
  user_name?: string;
  functional_area?: string;
  project_id?: string;
  project_name?: string;
  is_absence?: boolean;
  is_other?: boolean;
  cells: Record<string, number>;
  comments?: Record<string, string>;
  weekSums?: Record<string, number>;
}

export function CommentOverlay({
  comment,
  isDark,
}: {
  readonly comment: string;
  readonly isDark: boolean;
}): JSX.Element {
  return (
    <div
      aria-hidden
      className="absolute top-0 flex h-full items-center px-2 text-xs shadow-sm"
      style={{
        left: '100%',
        width: 10 * 42,
        backgroundColor: isDark ? '#451a03' : '#fffbeb',
        color: isDark ? '#fef3c7' : '#78350f',
        zIndex: 25,
      }}
      title={comment}
    >
      <span
        className="absolute"
        style={{
          left: -6,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 0,
          height: 0,
          borderTop: '6px solid transparent',
          borderBottom: '6px solid transparent',
          borderRight: `6px solid ${isDark ? '#451a03' : '#fffbeb'}`,
        }}
      />
      <span className="truncate">{comment}</span>
    </div>
  );
}

function weekHeaderClassName(hasComment: boolean, isExpanded: boolean): string {
  if (!hasComment) return 'invisible';
  if (isExpanded) return 'text-red-500 dark:text-white';
  return 'text-red-500/80 hover:text-red-500 dark:text-white/80 dark:hover:text-white';
}

export interface WeekColumnMeta {
  readonly week: string;
  readonly weekLabel: string;
  readonly hasComment: boolean;
  readonly isExpanded: boolean;
  readonly onToggle: (week: string) => void;
}

export function WeekHeader(ctx: HeaderContext<FlatRow, unknown>): JSX.Element {
  const meta = ctx.column.columnDef.meta as WeekColumnMeta;
  const { week, weekLabel, hasComment, isExpanded, onToggle } = meta;
  const handleClick = (e: React.MouseEvent): void => {
    if (!hasComment) return;
    e.stopPropagation();
    onToggle(week);
  };
  return (
    <div className="flex flex-col leading-none gap-0.5">
      <button
        type="button"
        aria-label={`Toggle comments for ${weekLabel}`}
        tabIndex={hasComment ? 0 : -1}
        onClick={handleClick}
        className={`h-3.5 flex items-center justify-end ${weekHeaderClassName(hasComment, isExpanded)}`}
      >
        {isExpanded ? (
          <ArrowRightFromLine className="h-3.5 w-3.5" strokeWidth={2.5} />
        ) : (
          <ArrowLeftFromLine className="h-3.5 w-3.5" strokeWidth={2.5} />
        )}
      </button>
      <span>{weekLabel}</span>
    </div>
  );
}

function FACellRenderer({ row }: { readonly row: FlatRow }): JSX.Element | null {
  if (row._type === 'data') {
    return (
      <span className="text-xs text-muted-foreground">
        {row.functional_area}
      </span>
    );
  }
  return null;
}

export function FACell(ctx: CellContext<FlatRow, unknown>): JSX.Element | null {
  return <FACellRenderer row={ctx.row.original} />;
}

export interface NameColumnMeta {
  readonly groupBy: string;
  readonly warningSet: Set<string>;
  readonly onDeleteRow: (projectId: string, userId: string) => void;
}

function NameCellRenderer({
  row,
  groupBy,
  warningSet,
  onDeleteRow,
}: {
  readonly row: FlatRow;
  readonly groupBy: string;
  readonly warningSet: Set<string>;
  readonly onDeleteRow: (projectId: string, userId: string) => void;
}): JSX.Element | null {
  if (row._type !== 'data') return null;

  const isPinned = row.is_absence || row.is_other;
  const defaultLabel = groupBy === 'project' ? row.user_name : row.project_name;
  const label = isPinned && row.is_other ? 'Others' : defaultLabel;
  const userHasWarning = row.user_id ? warningSet.has(row.user_id) : false;

  return (
    <div className="flex items-center justify-between gap-1 min-w-0" title={label ?? undefined}>
      <span className="flex min-w-0 items-center gap-1 truncate">
        {groupBy === 'project' && userHasWarning && (
          <span title="Allocations exceed 100%"><AlertTriangle className="h-3 w-3 shrink-0 text-yellow-500" /></span>
        )}
        {groupBy === 'user' && !isPinned ? (
          <Link
            to={`/tracker/projects/${row.project_id}`}
            className="block min-w-0 truncate text-sm hover:underline"
          >
            {label}
          </Link>
        ) : (
          <span className={`block min-w-0 truncate text-sm ${isPinned ? 'italic text-muted-foreground' : ''}`}>
            {label}
          </span>
        )}
      </span>
      {!isPinned && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button
              className="shrink-0 opacity-0 group-hover/row:opacity-100 transition-opacity"
            >
              <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Remove row?</AlertDialogTitle>
              <AlertDialogDescription>
                This will delete all planned allocations for this combination.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  if (row.project_id && row.user_id) {
                    onDeleteRow(row.project_id, row.user_id);
                  }
                }}
              >
                Remove
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </div>
  );
}

export function NameCell(ctx: CellContext<FlatRow, unknown>): JSX.Element | null {
  const meta = ctx.column.columnDef.meta as NameColumnMeta;
  return (
    <NameCellRenderer
      row={ctx.row.original}
      groupBy={meta.groupBy}
      warningSet={meta.warningSet}
      onDeleteRow={meta.onDeleteRow}
    />
  );
}
