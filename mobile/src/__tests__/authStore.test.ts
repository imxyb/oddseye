import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  deleteItemAsync: vi.fn(),
  getItemAsync: vi.fn(),
  getMe: vi.fn(),
  loginRequest: vi.fn(),
  setItemAsync: vi.fn(),
}));

vi.mock("expo-secure-store", () => ({
  deleteItemAsync: mocks.deleteItemAsync,
  getItemAsync: mocks.getItemAsync,
  setItemAsync: mocks.setItemAsync,
}));

vi.mock("../api/client", () => ({
  ACCESS_TOKEN_KEY: "access_token",
}));

vi.mock("../api/auth", () => ({
  getMe: mocks.getMe,
  loginRequest: mocks.loginRequest,
}));

import { useAuthStore } from "../stores/authStore";

function resetAuthStore() {
  useAuthStore.setState({
    error: null,
    isAuthenticated: false,
    isBootstrapped: false,
    status: "idle",
    token: null,
    user: null,
  });
}

describe("auth store", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetAuthStore();
  });

  it("stores the backend JWT after successful login", async () => {
    mocks.loginRequest.mockResolvedValue({
      access_token: "jwt-token",
      user: { role: "admin", username: "admin" },
    });

    await useAuthStore.getState().login("admin", "password");

    expect(mocks.loginRequest).toHaveBeenCalledWith("admin", "password");
    expect(mocks.setItemAsync).toHaveBeenCalledWith("access_token", "jwt-token");
    expect(useAuthStore.getState()).toMatchObject({
      isAuthenticated: true,
      status: "authenticated",
      token: "jwt-token",
      user: { role: "admin", username: "admin" },
    });
  });

  it("restores an authenticated session from SecureStore", async () => {
    mocks.getItemAsync.mockResolvedValue("stored-token");
    mocks.getMe.mockResolvedValue({ role: "admin", username: "admin" });

    await useAuthStore.getState().bootstrap();

    expect(mocks.getItemAsync).toHaveBeenCalledWith("access_token");
    expect(mocks.getMe).toHaveBeenCalled();
    expect(useAuthStore.getState()).toMatchObject({
      isAuthenticated: true,
      status: "authenticated",
      token: "stored-token",
      user: { role: "admin", username: "admin" },
    });
  });

  it("clears stale stored tokens after a failed login", async () => {
    mocks.loginRequest.mockRejectedValue(new Error("bad credentials"));

    await expect(useAuthStore.getState().login("admin", "wrong")).rejects.toThrow(
      "bad credentials",
    );

    expect(mocks.deleteItemAsync).toHaveBeenCalledWith("access_token");
    expect(useAuthStore.getState()).toMatchObject({
      error: "bad credentials",
      isAuthenticated: false,
      status: "anonymous",
      token: null,
      user: null,
    });
  });
});
