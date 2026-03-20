import { Outlet, Navigate, useMatch } from 'react-router-dom';

export default function TrackerLayout(): JSX.Element {
  const isIndex = useMatch('/admin/tracker');

  if (isIndex) {
    return <Navigate to="periods" replace />;
  }

  return <Outlet />;
}
