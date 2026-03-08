import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';

// --- Data interfaces ---

interface JiraUser {
  account_id: string;
  email: string;
  display_name: string;
  account_type: string;
  is_external: boolean;
}

interface JiraGroup {
  group_id: string;
  name: string;
}

interface JiraGroupMember {
  account_id: string;
  display_name: string;
}

export interface JiraSnapshotData {
  users: JiraUser[];
  groups: JiraGroup[];
  group_members: Record<string, JiraGroupMember[]>;
}

type TabKey = 'users' | 'groups' | 'group_members';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'users', label: 'Users' },
  { key: 'groups', label: 'Groups' },
  { key: 'group_members', label: 'Group Members' },
];

// --- Users table ---

function UsersTable({ users }: { readonly users: JiraUser[] }): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Display Name</th>
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Account Type</th>
            <th className="pb-3 font-medium">External</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.account_id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm font-medium">{u.display_name}</td>
              <td className="py-3 pr-4 text-sm text-muted-foreground">
                {u.email || '\u2014'}
              </td>
              <td className="py-3 pr-4">
                <Badge variant="outline">{u.account_type}</Badge>
              </td>
              <td className="py-3 pr-4">
                {u.is_external && <Badge variant="default">External</Badge>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Groups table ---

function GroupsTable({
  groups,
  groupMembers,
}: {
  readonly groups: JiraGroup[];
  readonly groupMembers: Record<string, JiraGroupMember[]>;
}): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Members</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.group_id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm font-medium">{g.name}</td>
              <td className="py-3 pr-4 text-sm">
                {groupMembers[g.group_id]?.length ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Group Members (expandable) ---

function GroupMembersList({
  groupMembers,
}: {
  readonly groupMembers: Record<string, JiraGroupMember[]>;
}): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleGroup = (groupId: string): void => {
    setExpanded((prev) => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  const groupIds = Object.keys(groupMembers).sort((a, b) => a.localeCompare(b));

  return (
    <div className="space-y-1">
      {groupIds.map((groupId) => {
        const members = groupMembers[groupId];
        const isExpanded = expanded[groupId] ?? false;

        return (
          <div key={groupId}>
            <button
              type="button"
              className="flex items-center gap-2 w-full py-3 pr-4 text-sm text-left hover:bg-muted/50 rounded-md px-2"
              onClick={() => toggleGroup(groupId)}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              <span className="font-medium">{groupId}</span>
              <span className="text-muted-foreground ml-auto">
                {members.length} member{members.length === 1 ? '' : 's'}
              </span>
            </button>
            {isExpanded && (
              <div className="ml-8 mb-2">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b">
                      <th className="pb-2 font-medium">Account ID</th>
                      <th className="pb-2 font-medium">Display Name</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr
                        key={`${groupId}-${m.account_id}`}
                        className="border-b last:border-b-0"
                      >
                        <td className="py-2 pr-4 text-sm">{m.account_id}</td>
                        <td className="py-2 pr-4 text-sm">{m.display_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Main tabbed component ---

interface JiraDataTabsProps {
  readonly data: JiraSnapshotData;
}

export default function JiraDataTabs({ data }: JiraDataTabsProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabKey>('users');

  const users = data.users ?? [];
  const groups = data.groups ?? [];
  const groupMembers = data.group_members ?? {};

  return (
    <>
      <div className="flex gap-1 border-b">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'users' && <UsersTable users={users} />}
      {activeTab === 'groups' && (
        <GroupsTable groups={groups} groupMembers={groupMembers} />
      )}
      {activeTab === 'group_members' && (
        <GroupMembersList groupMembers={groupMembers} />
      )}
    </>
  );
}
