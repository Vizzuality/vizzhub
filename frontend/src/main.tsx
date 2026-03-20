import React from 'react';
import ReactDOM from 'react-dom/client';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from './shared/components/theme-provider';
import App from './App';
import { NavigationGuardProvider } from './core/contexts/NavigationGuardContext';
import { TIMING } from './shared/constants/timing';
import './index.css';

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: TIMING.QUERY_STALE_TIME,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <GoogleOAuthProvider clientId={googleClientId}>
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <NavigationGuardProvider>
              <App />
            </NavigationGuardProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ThemeProvider>
    </GoogleOAuthProvider>
  </React.StrictMode>,
);
