"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";
import { useAuth } from "@/lib/auth/AuthContext";
import { BusinessStore, type BusinessContextType } from "./business-store";

export type { BusinessContextType, BusinessState } from "./business-store";
export { BusinessStore } from "./business-store";

const BusinessContext = createContext<BusinessContextType | undefined>(undefined);

export function BusinessProvider({
  children,
  store: initialStore,
}: {
  children: React.ReactNode;
  store?: BusinessStore;
}) {
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const store = useMemo(() => initialStore ?? new BusinessStore(), [initialStore]);

  // Synchronize authentication status with business store
  useEffect(() => {
    store.handleAuthChange(isAuthenticated && !isAuthLoading, user?.id ?? null);
  }, [store, isAuthenticated, isAuthLoading, user?.id]);

  const state = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot
  );

  const value: BusinessContextType = useMemo(
    () => ({
      ...state,
      refreshBusinesses: store.refreshBusinesses,
      createBusiness: store.createBusiness,
    }),
    [state, store]
  );

  return (
    <BusinessContext.Provider value={value}>
      {children}
    </BusinessContext.Provider>
  );
}

export function useBusiness(): BusinessContextType {
  const context = useContext(BusinessContext);
  if (!context) {
    throw new Error("useBusiness must be used within a BusinessProvider");
  }
  return context;
}
