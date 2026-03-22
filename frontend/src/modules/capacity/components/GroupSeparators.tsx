export function GroupSeparators(props: Record<string, unknown>): JSX.Element | null {
  const xAxisMap = props.xAxisMap as Record<string, Record<string, unknown>> | undefined;
  const offset = props.offset as { top: number; height: number } | undefined;
  if (!xAxisMap || !offset) return null;

  const xAxis = Object.values(xAxisMap)[0];
  const scale = xAxis?.scale as ((v: string) => number) & { domain: () => string[]; bandwidth: () => number } | undefined;
  if (!scale?.domain || !scale?.bandwidth) return null;

  const domain = scale.domain();
  const bandwidth = scale.bandwidth();
  if (domain.length < 2) return null;

  return (
    <g>
      {domain.slice(1).map((cat, i) => {
        const prevEnd = scale(domain[i]) + bandwidth;
        const currStart = scale(cat);
        const lineX = (prevEnd + currStart) / 2;
        return (
          <line
            key={cat}
            x1={lineX}
            y1={offset.top}
            x2={lineX}
            y2={offset.top + offset.height}
            stroke="currentColor"
            strokeDasharray="4 4"
            strokeOpacity={0.2}
          />
        );
      })}
    </g>
  );
}
