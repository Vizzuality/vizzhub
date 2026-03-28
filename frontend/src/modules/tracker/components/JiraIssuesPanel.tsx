import { useMemo } from 'react';
import { useJiraIssues } from '../hooks/useJiraIssues';
import type { JiraIssue } from '../types/tracker';

interface JiraIssuesPanelProps {
  readonly periodDate: string;
}

const STATUS_DOT_COLOR: Record<string, string> = {
  'To Do': 'bg-gray-400',
  'In Progress': 'bg-blue-400',
  'Done': 'bg-green-500',
};

function statusDotClass(category: string): string {
  return STATUS_DOT_COLOR[category] ?? 'bg-gray-400';
}

export default function JiraIssuesPanel({
  periodDate,
}: JiraIssuesPanelProps): JSX.Element | null {
  const { data, isLoading } = useJiraIssues(periodDate);

  const grouped = useMemo(() => {
    if (!data?.issues?.length) return [];
    const map = new Map<string, { name: string; issues: JiraIssue[] }>();
    for (const issue of data.issues) {
      const key = issue.project_key;
      if (!map.has(key)) {
        map.set(key, { name: issue.project_name, issues: [] });
      }
      map.get(key)!.issues.push(issue);
    }
    return Array.from(map.entries()).sort((a, b) =>
      a[1].name.localeCompare(b[1].name),
    );
  }, [data]);

  if (isLoading) {
    return (
      <div className="text-xs text-muted-foreground">Loading Jira issues...</div>
    );
  }

  if (!data?.issues?.length) return null;

  const siteUrl = data.site_url?.replace(/\/$/, '') ?? '';

  return (
    <div className="overflow-hidden">
      <h3 className="text-xs font-medium text-muted-foreground mb-2">From Jira</h3>
      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
        {grouped.map(([projectKey, group]) => (
          <div key={projectKey}>
            <div className="text-xs font-medium text-foreground mb-1">
              {group.name}
            </div>
            <div className="space-y-0.5">
              {group.issues.map((issue) => (
                <div
                  key={issue.key}
                  className="flex items-start gap-1.5 text-xs min-w-0"
                >
                  <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 mt-1.5 ${statusDotClass(issue.status_category)}`} />
                  {siteUrl ? (
                    <a
                      href={`${siteUrl}/browse/${issue.key}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-foreground shrink-0 underline decoration-dotted"
                    >
                      {issue.key}
                    </a>
                  ) : (
                    <span className="text-muted-foreground shrink-0">{issue.key}</span>
                  )}
                  <span className="text-foreground truncate">{issue.summary}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
