import { beforeEach, describe, expect, it, vi } from "vitest";

const getItemAsync = vi.fn();

vi.mock("expo-secure-store", () => ({
  getItemAsync,
}));

describe("apiFetch", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.EXPO_PUBLIC_API_BASE_URL = "https://api.example.test/";
    global.fetch = vi.fn();
  });

  it("builds requests from the public API base URL and JWT from SecureStore", async () => {
    getItemAsync.mockResolvedValue("jwt-token");
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { apiFetch } = await import("../api/client");

    await apiFetch("/radar/markets?limit=1");

    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.example.test/radar/markets?limit=1",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer jwt-token",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("throws a friendly ApiError when the backend returns JSON detail", async () => {
    getItemAsync.mockResolvedValue(null);
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid credentials" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { ApiError, apiFetch } = await import("../api/client");

    let thrown: unknown;
    try {
      await apiFetch("/auth/me");
    } catch (error) {
      thrown = error;
    }

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown).toHaveProperty("message", "Invalid credentials");
  });

  it("does not show raw response bodies for non-JSON failures", async () => {
    getItemAsync.mockResolvedValue(null);
    vi.mocked(global.fetch).mockResolvedValue(
      new Response("<html>traceback</html>", { status: 500 }),
    );

    const { apiFetch } = await import("../api/client");

    await expect(apiFetch("/auth/me")).rejects.toThrow("Request failed");
  });
});
