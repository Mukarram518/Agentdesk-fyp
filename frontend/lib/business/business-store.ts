/**
 * AgentDesk Business State Store.
 * Centralized, pure state management for user business memberships and current active workspace.
 */

import type { BusinessResponse, BusinessCreatePayload } from "@/types/business";
import { apiClient, isApiClientError, type ApiClient } from "@/lib/api/client";

export interface BusinessState {
  businesses: BusinessResponse[];
  currentBusiness: BusinessResponse | null;
  isLoadingBusiness: boolean;
  businessError: string | null;
}

export interface BusinessContextType extends BusinessState {
  refreshBusinesses: () => Promise<void>;
  createBusiness: (payload: BusinessCreatePayload) => Promise<BusinessResponse>;
}

export class BusinessStore {
  private state: BusinessState;
  private listeners = new Set<() => void>();
  private activeRequestId = 0;
  private isAuthenticated = false;
  private currentUserId: string | null = null;
  private client: ApiClient;

  constructor(client: ApiClient = apiClient) {
    this.client = client;
    this.state = {
      businesses: [],
      currentBusiness: null,
      isLoadingBusiness: false,
      businessError: null,
    };
  }

  getSnapshot = (): BusinessState => {
    return this.state;
  };

  getServerSnapshot = (): BusinessState => {
    return {
      businesses: [],
      currentBusiness: null,
      isLoadingBusiness: false,
      businessError: null,
    };
  };

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private setState(partial: Partial<BusinessState>) {
    this.state = { ...this.state, ...partial };
    for (const listener of this.listeners) {
      listener();
    }
  }

  /**
   * Responds to changes in authentication status.
   * - Immediately cancels in-flight operations and wipes business data upon logout.
   * - Automatically loads businesses when a new authenticated user session is detected.
   */
  handleAuthChange = (isAuthenticated: boolean, userId: string | null) => {
    if (!isAuthenticated || !userId) {
      // User is logged out or unauthenticated
      this.activeRequestId++; // Invalidate any in-flight promises
      this.isAuthenticated = false;
      this.currentUserId = null;
      this.setState({
        businesses: [],
        currentBusiness: null,
        isLoadingBusiness: false,
        businessError: null,
      });
      return;
    }

    // User is authenticated
    const userChanged = this.currentUserId !== userId;
    this.isAuthenticated = true;
    this.currentUserId = userId;

    if (userChanged || (!this.state.businesses.length && !this.state.currentBusiness)) {
      this.refreshBusinesses();
    }
  };

  /**
   * Fetches active businesses and the primary current business.
   * - Drops stale responses if auth state changes or a newer refresh was initiated.
   * - Treats 404 from /current as a normal empty state (not an error and never triggers logout).
   */
  refreshBusinesses = async (): Promise<void> => {
    if (!this.isAuthenticated || !this.currentUserId) {
      this.setState({
        businesses: [],
        currentBusiness: null,
        isLoadingBusiness: false,
        businessError: null,
      });
      return;
    }

    const reqId = ++this.activeRequestId;
    this.setState({ isLoadingBusiness: true, businessError: null });

    try {
      const [listResult, currentResult] = await Promise.allSettled([
        this.client.listBusinesses(),
        this.client.getCurrentBusiness(),
      ]);

      // Guard against stale response if user logged out or a newer request was dispatched
      if (reqId !== this.activeRequestId || !this.isAuthenticated) {
        return;
      }

      let nextBusinesses = this.state.businesses;
      let nextCurrent = this.state.currentBusiness;
      let nextError: string | null = null;

      // 1. Process business listing
      if (listResult.status === "fulfilled") {
        nextBusinesses = listResult.value;
      } else {
        const err = listResult.reason;
        nextError = isApiClientError(err) ? err.message : "Failed to load businesses.";
      }

      // 2. Process current business
      if (currentResult.status === "fulfilled") {
        nextCurrent = currentResult.value;
      } else {
        const err = currentResult.reason;
        // 404 indicates user has not created/selected an active business yet (normal state)
        if (isApiClientError(err) && err.statusCode === 404) {
          nextCurrent = null;
        } else {
          const errMessage = isApiClientError(err) ? err.message : "Failed to load current business.";
          nextError = nextError || errMessage;
        }
      }

      this.setState({
        businesses: nextBusinesses,
        currentBusiness: nextCurrent,
        businessError: nextError,
        isLoadingBusiness: false,
      });
    } catch (err: unknown) {
      if (reqId !== this.activeRequestId || !this.isAuthenticated) {
        return;
      }
      const message = isApiClientError(err) ? err.message : "An unexpected error occurred.";
      this.setState({
        businessError: message,
        isLoadingBusiness: false,
      });
    }
  };

  /**
   * Creates a new business, updates state immediately, and refreshes memberships.
   */
  createBusiness = async (payload: BusinessCreatePayload): Promise<BusinessResponse> => {
    if (!this.isAuthenticated || !this.currentUserId) {
      throw new Error("Authentication required to create a business.");
    }

    const reqId = ++this.activeRequestId;
    this.setState({ isLoadingBusiness: true, businessError: null });

    try {
      const newBiz = await this.client.createBusiness(payload);

      // Guard if user logged out or a newer operation was dispatched while creation was in flight
      if (!this.isAuthenticated || reqId !== this.activeRequestId) {
        return newBiz;
      }

      // Optimistically update current business and prepend to list
      const updatedList = [
        newBiz,
        ...this.state.businesses.filter((b) => b.id !== newBiz.id),
      ];

      this.setState({
        currentBusiness: newBiz,
        businesses: updatedList,
        businessError: null,
      });

      // Synchronize in background to ensure database consistency
      await this.refreshBusinesses();

      return newBiz;
    } catch (err: unknown) {
      // If user logged out or request is stale, do not restore state or error
      if (!this.isAuthenticated || reqId !== this.activeRequestId) {
        throw err;
      }

      const message = isApiClientError(err) ? err.message : "Failed to create business.";
      this.setState({
        businessError: message,
        isLoadingBusiness: false,
      });
      throw err;
    }
  };
}
