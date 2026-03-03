/**
 * Login page with Google Sign-In
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useAuth } from '../hooks/useAuth';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';

export function LoginPage(): JSX.Element {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  const handleSuccess = async (response: CredentialResponse): Promise<void> => {
    if (!response.credential) {
      setError('No credential received from Google');
      return;
    }

    try {
      setError(null);
      await login(response.credential);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    }
  };

  const handleError = (): void => {
    setError('Google Sign-In failed');
  };

  if (isLoading) {
    return <LoadingSpinner className="min-h-screen" />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-8 p-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">Project Scorecard</h1>
          <p className="mt-2 text-muted-foreground">Sign in to continue</p>
        </div>

        {error && (
          <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm text-center">
            {error}
          </div>
        )}

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleSuccess}
            onError={handleError}
            useOneTap
            theme="filled_black"
            shape="rectangular"
            size="large"
            text="signin_with"
          />
        </div>
      </div>
    </div>
  );
}
