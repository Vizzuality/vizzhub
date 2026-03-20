import { createContext, useContext, useCallback, useRef } from 'react';

interface NavigationGuardContextType {
  setGuard: (guard: (() => boolean) | null) => void;
  confirmNavigation: () => boolean;
}

const NavigationGuardContext = createContext<NavigationGuardContextType>({
  setGuard: () => {},
  confirmNavigation: () => true,
});

export function NavigationGuardProvider({
  children,
}: {
  readonly children: React.ReactNode;
}): JSX.Element {
  const guardRef = useRef<(() => boolean) | null>(null);

  const setGuard = useCallback((guard: (() => boolean) | null) => {
    guardRef.current = guard;
  }, []);

  const confirmNavigation = useCallback(() => {
    if (guardRef.current) {
      return guardRef.current();
    }
    return true;
  }, []);

  return (
    <NavigationGuardContext.Provider value={{ setGuard, confirmNavigation }}>
      {children}
    </NavigationGuardContext.Provider>
  );
}

export function useNavigationGuard(): NavigationGuardContextType {
  return useContext(NavigationGuardContext);
}
