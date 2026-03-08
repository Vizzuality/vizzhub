import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';

// --- Data interfaces ---

interface GitHubMember {
  login: string;
  id: number;
  name: string | null;
  email: string | null;
  role: string;
}

interface GitHubTeam {
  id: number;
  name: string;
  slug: string;
  parent_slug: string | null;
  description: string;
  privacy: string;
}

interface GitHubTeamMember {
  login: string;
  role: string;
}

interface GitHubOutsideCollaborator {
  login: string;
  id: number;
  name: string | null;
  email: string | null;
}

export interface GitHubSnapshotData {
  members: GitHubMember[];
  teams: GitHubTeam[];
  team_members: Record<string, GitHubTeamMember[]>;
  outside_collaborators: GitHubOutsideCollaborator[];
}

type TabKey = 'members' | 'teams' | 'team_members' | 'outside';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'members', label: 'Members' },
  { key: 'teams', label: 'Teams' },
  { key: 'team_members', label: 'Team Members' },
  { key: 'outside', label: 'Outside Collaborators' },
];

// --- Members table ---

function MembersTable({ members }: { readonly members: GitHubMember[] }): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Login</th>
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Email</th>
            <th className="pb-3 font-medium">Role</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm">{m.login}</td>
              <td className="py-3 pr-4 text-sm text-muted-foreground">
                {m.name || '\u2014'}
              </td>
              <td className="py-3 pr-4 text-sm text-muted-foreground">
                {m.email || '\u2014'}
              </td>
              <td className="py-3 pr-4">
                {m.role === 'admin' ? (
                  <Badge variant="default">Owner</Badge>
                ) : (
                  <Badge variant="outline">{m.role}</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Teams table ---

function TeamsTable({
  teams,
  teamMembers,
}: {
  readonly teams: GitHubTeam[];
  readonly teamMembers: Record<string, GitHubTeamMember[]>;
}): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Slug</th>
            <th className="pb-3 font-medium">Parent</th>
            <th className="pb-3 font-medium">Privacy</th>
            <th className="pb-3 font-medium">Members</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((t) => (
            <tr key={t.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm font-medium">{t.name}</td>
              <td className="py-3 pr-4 text-sm">{t.slug}</td>
              <td className="py-3 pr-4 text-sm">{t.parent_slug || '\u2014'}</td>
              <td className="py-3 pr-4">
                <Badge variant="outline">{t.privacy}</Badge>
              </td>
              <td className="py-3 pr-4 text-sm">
                {teamMembers[t.slug]?.length ?? 0}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Team Members (expandable) ---

function TeamMembersList({
  teamMembers,
}: {
  readonly teamMembers: Record<string, GitHubTeamMember[]>;
}): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleTeam = (slug: string): void => {
    setExpanded((prev) => ({ ...prev, [slug]: !prev[slug] }));
  };

  const slugs = Object.keys(teamMembers).sort((a, b) => a.localeCompare(b));

  return (
    <div className="space-y-1">
      {slugs.map((slug) => {
        const members = teamMembers[slug];
        const isExpanded = expanded[slug] ?? false;

        return (
          <div key={slug}>
            <button
              type="button"
              className="flex items-center gap-2 w-full py-3 pr-4 text-sm text-left hover:bg-muted/50 rounded-md px-2"
              onClick={() => toggleTeam(slug)}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 shrink-0" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0" />
              )}
              <span className="font-medium">{slug}</span>
              <span className="text-muted-foreground ml-auto">
                {members.length} member{members.length === 1 ? '' : 's'}
              </span>
            </button>
            {isExpanded && (
              <div className="ml-8 mb-2">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b">
                      <th className="pb-2 font-medium">Login</th>
                      <th className="pb-2 font-medium">Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => (
                      <tr
                        key={`${slug}-${m.login}`}
                        className="border-b last:border-b-0"
                      >
                        <td className="py-2 pr-4 text-sm">{m.login}</td>
                        <td className="py-2 pr-4 text-sm">{m.role}</td>
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

// --- Outside Collaborators table ---

function OutsideCollaboratorsTable({
  collaborators,
}: {
  readonly collaborators: GitHubOutsideCollaborator[];
}): JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="text-left text-sm text-muted-foreground border-b">
            <th className="pb-3 font-medium">Login</th>
            <th className="pb-3 font-medium">Name</th>
            <th className="pb-3 font-medium">Email</th>
          </tr>
        </thead>
        <tbody>
          {collaborators.map((c) => (
            <tr key={c.id} className="border-b last:border-b-0">
              <td className="py-3 pr-4 text-sm">{c.login}</td>
              <td className="py-3 pr-4 text-sm text-muted-foreground">
                {c.name || '\u2014'}
              </td>
              <td className="py-3 pr-4 text-sm text-muted-foreground">
                {c.email || '\u2014'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Main tabbed component ---

interface GitHubDataTabsProps {
  readonly data: GitHubSnapshotData;
}

export default function GitHubDataTabs({ data }: GitHubDataTabsProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabKey>('members');

  const members = data.members ?? [];
  const teams = data.teams ?? [];
  const teamMembers = data.team_members ?? {};
  const outsideCollaborators = data.outside_collaborators ?? [];

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

      {activeTab === 'members' && <MembersTable members={members} />}
      {activeTab === 'teams' && (
        <TeamsTable teams={teams} teamMembers={teamMembers} />
      )}
      {activeTab === 'team_members' && (
        <TeamMembersList teamMembers={teamMembers} />
      )}
      {activeTab === 'outside' && (
        <OutsideCollaboratorsTable collaborators={outsideCollaborators} />
      )}
    </>
  );
}
