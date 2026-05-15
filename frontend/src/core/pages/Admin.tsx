import { Outlet, Navigate, useMatch } from 'react-router-dom';
import { Action, usePermission } from '@/core/permissions';

export default function Admin(): JSX.Element {
  const isIndex = useMatch('/admin');
  const canAdmin = usePermission(Action.ADMIN_USERS);

  if (isIndex) {
    return <Navigate to={canAdmin ? 'scorecard-parameters' : 'tracker/periods'} replace />;
  }

  return <Outlet />;
}
