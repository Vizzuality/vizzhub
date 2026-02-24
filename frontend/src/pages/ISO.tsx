import { Outlet, Navigate, useMatch } from 'react-router-dom';

export default function ISO(): JSX.Element {
  const isIndex = useMatch('/iso');

  if (isIndex) {
    return <Navigate to="snapshots" replace />;
  }

  return <Outlet />;
}
