import test, { describe, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { BusinessStore } from "../lib/business/business-store";
import { ApiClient, ApiHttpError, ApiNetworkError } from "../lib/api/client";
import type { BusinessResponse } from "../types/business";

describe("Frontend Business State Store", () => {
  let mockClient: ApiClient;

  const sampleBusinesses: BusinessResponse[] = [
    {
      id: "biz-1",
      name: "Alpha Clinic",
      slug: "alpha-clinic",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T10:00:00Z",
      updated_at: "2026-10-13T10:00:00Z",
    },
    {
      id: "biz-2",
      name: "Beta Dental",
      slug: "beta-dental",
      is_active: true,
      role: "member",
      created_at: "2026-10-13T11:00:00Z",
      updated_at: "2026-10-13T11:00:00Z",
    },
  ];

  beforeEach(() => {
    mockClient = new ApiClient("http://127.0.0.1:8000");
  });

  test("authenticated user loads businesses and current business", async () => {
    mockClient.listBusinesses = async () => sampleBusinesses;
    mockClient.getCurrentBusiness = async () => sampleBusinesses[0];

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");

    // Wait for async load to settle
    await store.refreshBusinesses();

    const state = store.getSnapshot();
    assert.strictEqual(state.isLoadingBusiness, false);
    assert.strictEqual(state.businessError, null);
    assert.strictEqual(state.businesses.length, 2);
    assert.strictEqual(state.currentBusiness?.id, "biz-1");
    assert.strictEqual(state.currentBusiness?.name, "Alpha Clinic");
  });

  test("user with no business receives empty/no-current-business state without error", async () => {
    mockClient.listBusinesses = async () => [];
    mockClient.getCurrentBusiness = async () => {
      throw new ApiHttpError(404, "Not Found", {
        detail: "No active business found for this account. Please complete business onboarding.",
      });
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-nobiz");
    await store.refreshBusinesses();

    const state = store.getSnapshot();
    assert.strictEqual(state.isLoadingBusiness, false);
    assert.strictEqual(state.businessError, null);
    assert.strictEqual(state.businesses.length, 0);
    assert.strictEqual(state.currentBusiness, null);
  });

  test("unauthenticated user triggers no business API calls", async () => {
    let apiCalled = false;
    mockClient.listBusinesses = async () => {
      apiCalled = true;
      return [];
    };
    mockClient.getCurrentBusiness = async () => {
      apiCalled = true;
      return sampleBusinesses[0];
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(false, null);

    const state = store.getSnapshot();
    assert.strictEqual(apiCalled, false);
    assert.strictEqual(state.businesses.length, 0);
    assert.strictEqual(state.currentBusiness, null);
    assert.strictEqual(state.isLoadingBusiness, false);
  });

  test("logout clears business state immediately", async () => {
    mockClient.listBusinesses = async () => sampleBusinesses;
    mockClient.getCurrentBusiness = async () => sampleBusinesses[0];

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");
    await store.refreshBusinesses();

    assert.strictEqual(store.getSnapshot().businesses.length, 2);
    assert.strictEqual(store.getSnapshot().currentBusiness?.id, "biz-1");

    // Trigger logout
    store.handleAuthChange(false, null);

    const loggedOutState = store.getSnapshot();
    assert.strictEqual(loggedOutState.businesses.length, 0);
    assert.strictEqual(loggedOutState.currentBusiness, null);
    assert.strictEqual(loggedOutState.isLoadingBusiness, false);
    assert.strictEqual(loggedOutState.businessError, null);
  });

  test("business creation refreshes state and updates current business", async () => {
    const initialList: BusinessResponse[] = [];
    const newBiz: BusinessResponse = {
      id: "biz-new",
      name: "Created Clinic",
      slug: "created-clinic",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T12:00:00Z",
      updated_at: "2026-10-13T12:00:00Z",
    };

    mockClient.listBusinesses = async () => [newBiz];
    mockClient.getCurrentBusiness = async () => newBiz;
    mockClient.createBusiness = async () => newBiz;

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");

    const created = await store.createBusiness({ name: "Created Clinic" });

    assert.strictEqual(created.id, "biz-new");
    const state = store.getSnapshot();
    assert.strictEqual(state.currentBusiness?.id, "biz-new");
    assert.strictEqual(state.businesses.length, 1);
    assert.strictEqual(state.businesses[0].name, "Created Clinic");
  });

  test("API and network errors are exposed safely in state", async () => {
    mockClient.listBusinesses = async () => {
      throw new ApiNetworkError("Connection refused by server.");
    };
    mockClient.getCurrentBusiness = async () => {
      throw new ApiNetworkError("Connection refused by server.");
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-err");
    await store.refreshBusinesses();

    const state = store.getSnapshot();
    assert.strictEqual(state.isLoadingBusiness, false);
    assert.ok(state.businessError?.includes("Connection refused"));
  });

  test("async requests do not restore stale data after logout", async () => {
    let resolveList: (v: BusinessResponse[]) => void = () => {};
    let resolveCurrent: (v: BusinessResponse) => void = () => {};

    const listPromise = new Promise<BusinessResponse[]>((resolve) => {
      resolveList = resolve;
    });
    const currentPromise = new Promise<BusinessResponse>((resolve) => {
      resolveCurrent = resolve;
    });

    mockClient.listBusinesses = () => listPromise;
    mockClient.getCurrentBusiness = () => currentPromise;

    const store = new BusinessStore(mockClient);

    // 1. User starts authenticated load
    store.handleAuthChange(true, "user-slow");
    assert.strictEqual(store.getSnapshot().isLoadingBusiness, true);

    // 2. User logs out before slow promises resolve
    store.handleAuthChange(false, null);
    assert.strictEqual(store.getSnapshot().businesses.length, 0);
    assert.strictEqual(store.getSnapshot().currentBusiness, null);

    // 3. Slow network responses finally resolve
    resolveList(sampleBusinesses);
    resolveCurrent(sampleBusinesses[0]);

    // Give microtasks time to execute
    await new Promise((r) => setTimeout(r, 10));

    // 4. Stale responses MUST NOT have overwritten the logged-out state
    const finalState = store.getSnapshot();
    assert.strictEqual(finalState.businesses.length, 0);
    assert.strictEqual(finalState.currentBusiness, null);
    assert.strictEqual(finalState.isLoadingBusiness, false);
  });

  test("createBusiness failure (409/422) does not leave failed business in state", async () => {
    mockClient.createBusiness = async () => {
      throw new ApiHttpError(409, "Conflict", {
        detail: "A business with the slug 'conflict-slug' already exists.",
      });
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");

    await assert.rejects(
      async () => {
        await store.createBusiness({ name: "Conflict Clinic", slug: "conflict-slug" });
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiHttpError);
        assert.strictEqual(err.statusCode, 409);
        return true;
      }
    );

    const state = store.getSnapshot();
    assert.strictEqual(state.businesses.length, 0);
    assert.strictEqual(state.currentBusiness, null);
    assert.strictEqual(state.isLoadingBusiness, false);
    assert.ok(state.businessError?.includes("already exists"));
  });

  test("createBusiness success with subsequent refresh failure exposes refresh error while retaining created business", async () => {
    const newBiz: BusinessResponse = {
      id: "biz-created-ok",
      name: "Created Clinic",
      slug: "created-clinic",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T12:00:00Z",
      updated_at: "2026-10-13T12:00:00Z",
    };

    mockClient.createBusiness = async () => newBiz;
    // Refresh fails after creation
    mockClient.listBusinesses = async () => {
      throw new ApiNetworkError("Network interrupted after creation.");
    };
    mockClient.getCurrentBusiness = async () => {
      throw new ApiNetworkError("Network interrupted after creation.");
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");

    const result = await store.createBusiness({ name: "Created Clinic" });
    assert.strictEqual(result.id, "biz-created-ok");

    const state = store.getSnapshot();
    // Retains newly created business in state
    assert.strictEqual(state.currentBusiness?.id, "biz-created-ok");
    assert.strictEqual(state.businesses.length, 1);
    // Exposes the refresh error so UI does not silently misrepresent sync
    assert.ok(state.businessError?.includes("Network interrupted"));
    assert.strictEqual(state.isLoadingBusiness, false);
  });

  test("logout while createBusiness is in flight does not restore business data for logged-out user", async () => {
    let resolveCreate: (v: BusinessResponse) => void = () => {};
    const createPromise = new Promise<BusinessResponse>((resolve) => {
      resolveCreate = resolve;
    });

    mockClient.createBusiness = () => createPromise;
    mockClient.listBusinesses = async () => [];
    mockClient.getCurrentBusiness = async () => {
      throw new ApiHttpError(404, "Not Found");
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");

    const creationCall = store.createBusiness({ name: "Slow Created Business" });

    // User logs out while create request is in flight
    store.handleAuthChange(false, null);
    assert.strictEqual(store.getSnapshot().currentBusiness, null);
    assert.strictEqual(store.getSnapshot().businesses.length, 0);

    // Create call finally resolves
    const newBiz: BusinessResponse = {
      id: "biz-slow",
      name: "Slow Created Business",
      slug: "slow-created-business",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T12:00:00Z",
      updated_at: "2026-10-13T12:00:00Z",
    };
    resolveCreate(newBiz);

    await creationCall;
    await new Promise((r) => setTimeout(r, 10));

    // Must NOT restore business data into logged-out store
    const state = store.getSnapshot();
    assert.strictEqual(state.currentBusiness, null);
    assert.strictEqual(state.businesses.length, 0);
    assert.strictEqual(state.businessError, null);
    assert.strictEqual(state.isLoadingBusiness, false);
  });

  test("refresh started before creation completes cannot overwrite newly created business", async () => {
    let resolveRefreshList: (v: BusinessResponse[]) => void = () => {};
    const slowRefreshPromise = new Promise<BusinessResponse[]>((resolve) => {
      resolveRefreshList = resolve;
    });

    mockClient.listBusinesses = () => slowRefreshPromise;
    mockClient.getCurrentBusiness = async () => {
      throw new ApiHttpError(404, "Not Found");
    };

    const store = new BusinessStore(mockClient);
    store.handleAuthChange(true, "user-123");

    // Slow initial refresh is running (started before creation)
    const initialRefreshPromise = store.refreshBusinesses();

    // User creates a new business before slow refresh finishes
    const newBiz: BusinessResponse = {
      id: "biz-fast-created",
      name: "Fast Created",
      slug: "fast-created",
      is_active: true,
      role: "owner",
      created_at: "2026-10-13T12:00:00Z",
      updated_at: "2026-10-13T12:00:00Z",
    };
    mockClient.createBusiness = async () => newBiz;
    // Subsequent refresh will return the created business
    mockClient.listBusinesses = async () => [newBiz];
    mockClient.getCurrentBusiness = async () => newBiz;

    await store.createBusiness({ name: "Fast Created" });

    // Now the older refresh resolves with stale empty array
    resolveRefreshList([]);
    await initialRefreshPromise;
    await new Promise((r) => setTimeout(r, 10));

    // Stale empty array from older refresh must NOT overwrite the newly created business
    const state = store.getSnapshot();
    assert.strictEqual(state.currentBusiness?.id, "biz-fast-created");
    assert.strictEqual(state.businesses.length, 1);
    assert.strictEqual(state.businesses[0].id, "biz-fast-created");
  });
});
