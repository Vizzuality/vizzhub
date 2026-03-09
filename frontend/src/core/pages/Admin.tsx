import { Outlet, Navigate, useMatch } from 'react-router-dom';

export default function Admin(): JSX.Element {
  const isIndex = useMatch('/admin');

  if (isIndex) {
    return <Navigate to="global-scores" replace />;
  }

  return <Outlet />;
}
