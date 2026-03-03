import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';

// --- Data interfaces ---

interface SnapshotUser {
  id: string;
  name: string;
  email: string;
  suspended: boolean;
  org_unit_path: string;
}

interface SnapshotGroup {
  id: string;
  name: string;
  email: string;
}

interface GroupMember {
  role: string;
  type: string;
  email: string;
}

interface RoleAssignment {
  role_id: string;
  user_id: string;
  role_name: string;
  user_email: string;
}

export interface SnapshotData {
  users: SnapshotUser[];
  groups: SnapshotGroup[];
  group_members: Record<string, GroupMember[]>;
  role_assignments: RoleAssignment[];
}

type TabKey = 'users' | 'groups' | 'group_members' | 'admins';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'users', label: 'Users' },
  { key: 'groups', label: 'Groups' },
  { key: 'group_members', label: 'Group Members' },
  { key: 'admins', label: 'Admins' },
];

// --- Users table ---

interface UsersTableProps {
  readonly users: SnapshotUser[];
}

function UsersTable({ users }: UsersTableProps): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Status</th>
            <th className="pb-3 font-medium">Org Unit</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm">{user.name}</td>
              <td className="py-3 pr-4 text-sm">{user.email}</td>
              <td className="py-3 pr-4">
                {user.suspended ? (
                  <Badge variant="destructive">Suspended</Badge>
                ) : (
                  <Badge variant="outline">Active</Badge>
                )}
              </td>
              <td className="py-3 pr-4 text-sm">{user.org_unit_path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Groups table ---

interface GroupsTableProps {
  readonly groups: SnapshotGroup[];
  readonly groupMembers: Record<string, GroupMember[]>;
}

function GroupsTable({ groups, groupMembers }: GroupsTableProps): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Members</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr key={group.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm">{group.name}</td>
              <td className="py-3 pr-4 text-sm">{group.email}</td>
              <td className="py-3 pr-4 text-sm">
                {groupMembers[group.email]?.length ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Group Members list (expandable) ---

interface GroupMembersListProps {
  readonly groupMembers: Record<string, GroupMember[]>;
}

function GroupMembersList({ groupMembers }: GroupMembersListProps): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleGroup = (groupEmail: string): void => {
    setExpanded((prev) => ({ ...prev, [groupEmail]: !prev[groupEmail] }));
  };

  const groupEmails = Object.keys(groupMembers).sort((a, b) => a.localeCompare(b));

  return (
    <div className="space-y-1">
      {groupEmails.map((groupEmail) => {
        const members = groupMembers[groupEmail];
        const isExpanded = expanded[groupEmail] ?? false;

        return (
          <div key={groupEmail}>
            <button
              type="button"
              className="flex items-center gap-2 w-full py-3 pr-4 text-sm text-left hover:bg-muted/50 rounded-md px-2"
              onClick={() => toggleGroup(groupEmail)}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              <span className="font-medium">{groupEmail}</span>
              <span className="text-muted-foreground ml-auto">
                {members.length} member{members.length === 1 ? '' : 's'}
              </span>
            </button>
            {isExpanded && (
              <div className="ml-8 mb-2">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b">
                      <th className="pb-2 font-medium">Email</th>
                      <th className="pb-2 font-medium">Role</th>
                      <th className="pb-2 font-medium">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((member) => (
                      <tr
                        key={`${groupEmail}-${member.email}`}
                        className="border-b last:border-b-0"
                      >
                        <td className="py-2 pr-4 text-sm">{member.email}</td>
                        <td className="py-2 pr-4 text-sm">{member.role}</td>
                        <td className="py-2 pr-4">
                          {member.type === 'USER' ? (
                            <span className="text-sm">{member.type}</span>
                          ) : (
                            <Badge variant="secondary">External</Badge>
                          )}
                        </td>
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

// --- Admins table ---

interface AdminsTableProps {
  readonly roleAssignments: RoleAssignment[];
}

function AdminsTable({ roleAssignments }: AdminsTableProps): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Role Name</th>
          </tr>
        </thead>
        <tbody>
          {roleAssignments.map((ra) => (
            <tr
              key={`${ra.role_id}-${ra.user_id}`}
              className="border-b last:border-b-0"
            >
              <td className="py-3 pr-4 text-sm">{ra.user_email}</td>
              <td className="py-3 pr-4 text-sm">{ra.role_name}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Main tabbed component ---

interface SnapshotDataTabsProps {
  readonly data: SnapshotData;
}

export default function SnapshotDataTabs({ data }: SnapshotDataTabsProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabKey>('users');

  const users = data.users ?? [];
  const groups = data.groups ?? [];
  const groupMembers = data.group_members ?? {};
  const roleAssignments = data.role_assignments ?? [];

  return (
    <>
      {/* Tabs */}
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

      {/* Tab content */}
      {activeTab === 'users' && <UsersTable users={users} />}
      {activeTab === 'groups' && (
        <GroupsTable groups={groups} groupMembers={groupMembers} />
      )}
      {activeTab === 'group_members' && (
        <GroupMembersList groupMembers={groupMembers} />
      )}
      {activeTab === 'admins' && (
        <AdminsTable roleAssignments={roleAssignments} />
      )}
    </>
  );
}
