export interface WidgetProps {
  readonly nodeId: string;
  readonly isEditor: boolean;
}

export const WIDGET_REGISTRY: Record<string, React.ComponentType<WidgetProps>> = {};
