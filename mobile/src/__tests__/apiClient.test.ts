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

  it("throws a readable error when the backend returns a failure", async () => {
    getItemAsync.mockResolvedValue(null);
    vi.mocked(global.fetch).mockResolvedValue(
      new Response("nope", { status: 500 }),
    );

    const { apiFetch } = await import("../api/client");

    await expect(apiFetch("/auth/me")).rejects.toThrow("API 500: nope");
  });
});
