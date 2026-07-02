import { Navigate, useLocation } from 'react-router-dom';

interface RedirectWithSearchProps {
  readonly to: string;
}

export function RedirectWithSearch({ to }: RedirectWithSearchProps): JSX.Element {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
}
