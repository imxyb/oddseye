import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
  loadMobileEnv,
  verifyExpoGoSmoke,
} from "../../scripts/expoGoSmoke.mjs";

function tempProject() {
  const root = mkdtempSync(join(tmpdir(), "oddseye-expo-smoke-"));
  writeFileSync(
    join(root, "app.json"),
    JSON.stringify({
      expo: {
        name: "OddsEye",
        scheme: "oddseye",
        slug: "oddseye-mobile",
        ios: { bundleIdentifier: "fun.oddseye.app" },
      },
    }),
  );
  mkdirSync(join(root, "app"));
  return root;
}

describe("Expo Go smoke verifier", () => {
  it("loads the public API URL from mobile .env", () => {
    const root = tempProject();
    writeFileSync(join(root, ".env"), "EXPO_PUBLIC_API_BASE_URL=https://oddseye.fun\n");

    expect(loadMobileEnv(root)).toMatchObject({
      EXPO_PUBLIC_API_BASE_URL: "https://oddseye.fun",
    });
  });

  it("rejects missing deployed API URL before trying login", async () => {
    const root = tempProject();

    await expect(
      verifyExpoGoSmoke({
        env: { ODDSEYE_MOBILE_SMOKE_PASSWORD: "secret" },
        fetchImpl: vi.fn(),
        root,
      }),
    ).rejects.toThrow("EXPO_PUBLIC_API_BASE_URL");
  });

  it("checks health, login, and auth identity against the deployed API", async () => {
    const root = tempProject();
    writeFileSync(join(root, ".env"), "EXPO_PUBLIC_API_BASE_URL=https://oddseye.fun/\n");
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }))
      .mockResolvedValueOnce(jsonResponse({ access_token: "token-123" }))
      .mockResolvedValueOnce(jsonResponse({ username: "admin", role: "admin" }));

    const checks = await verifyExpoGoSmoke({
      env: { ODDSEYE_MOBILE_SMOKE_PASSWORD: "secret" },
      fetchImpl,
      root,
    });

    expect(checks.map((check) => check.name)).toEqual([
      "env",
      "expo_config",
      "health",
      "login",
      "auth_me",
    ]);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://oddseye.fun/health",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "https://oddseye.fun/auth/login",
      expect.objectContaining({
        body: JSON.stringify({ username: "admin", password: "secret" }),
        method: "POST",
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "https://oddseye.fun/auth/me",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer token-123" }),
        method: "GET",
      }),
    );
  });

  it("rejects a token that does not resolve to the expected user", async () => {
    const root = tempProject();
    writeFileSync(join(root, ".env"), "EXPO_PUBLIC_API_BASE_URL=https://oddseye.fun\n");
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }))
      .mockResolvedValueOnce(jsonResponse({ access_token: "token-123" }))
      .mockResolvedValueOnce(jsonResponse({ username: "other", role: "admin" }));

    await expect(
      verifyExpoGoSmoke({
        env: { ODDSEYE_MOBILE_SMOKE_PASSWORD: "secret" },
        fetchImpl,
        root,
      }),
    ).rejects.toThrow("expected admin");
  });
});

function jsonResponse(payload, ok = true, status = 200) {
  return {
    async json() {
      return payload;
    },
    ok,
    status,
    statusText: ok ? "OK" : "Error",
  };
}
