import { ExternalLink, Star } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { InstallMethodBadge } from './EntryBadges';
import type { DevstackEntry } from '../types/devstack';

interface EntryCardProps {
  readonly entry: DevstackEntry;
  readonly onClick: (id: string) => void;
}

export function EntryCard({ entry, onClick }: EntryCardProps): JSX.Element {
  const shaShort = entry.github_sha ? entry.github_sha.slice(0, 7) : null;

  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow flex flex-col"
      onClick={() => onClick(entry.id)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-sm leading-tight line-clamp-2">
            {entry.name}
          </h3>
          {entry.featured && (
            <Star size={14} className="shrink-0 text-amber-500 fill-amber-500" />
          )}
        </div>
        <div className="flex flex-wrap gap-1 mt-1">
          <Badge variant="outline" className="text-xs">
            {entry.type}
          </Badge>
          <InstallMethodBadge method={entry.install_method} />
          {entry.required && (
            <Badge className="text-xs bg-blue-600 hover:bg-blue-600 text-white">
              required
            </Badge>
          )}
          {!entry.active && (
            <Badge variant="outline" className="text-xs text-muted-foreground">
              inactive
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-0 flex-1 flex flex-col justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground line-clamp-3">
            {entry.description}
          </p>
          {entry.tech.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {entry.tech.map((tag) => (
                <Badge key={tag} variant="secondary" className="text-[10px]">
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          {shaShort ? (
            <span className="font-mono text-[10px] text-muted-foreground">
              {shaShort}
            </span>
          ) : (
            <span />
          )}
          {entry.url && (
            <a
              href={entry.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 -mr-2 rounded-md hover:bg-muted transition-colors"
            >
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
