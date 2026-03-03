import InfoTooltip from './InfoTooltip';

interface EVCardProps {
  label: string;
  tooltip: string;
  children: React.ReactNode;
}

export default function EVCard({ label, tooltip, children }: EVCardProps): JSX.Element {
  return (
    <div className="p-4 bg-muted/50 rounded-lg border">
      <div className="flex items-center gap-2 mb-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <InfoTooltip>
          <p className="text-sm">{tooltip}</p>
        </InfoTooltip>
      </div>
      {children}
    </div>
  );
}
