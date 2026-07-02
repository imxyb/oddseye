#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cwd, env, exit } from "node:process";

export function loadMobileEnv(rootDir) {
  const envPath = resolve(rootDir, ".env");
  if (!existsSync(envPath)) {
    return {};
  }

  const values = {};
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }
    values[match[1]] = unquoteEnvValue(match[2].trim());
  }
  return values;
}

export async function verifyExpoGoSmoke({
  env: providedEnv = env,
  fetchImpl = globalThis.fetch,
  root = cwd(),
} = {}) {
  if (typeof fetchImpl !== "function") {
    throw new Error("fetch is not available in this Node runtime");
  }

  const mergedEnv = { ...loadMobileEnv(root), ...providedEnv };
  const baseUrl = normalizeDeployedApiUrl(mergedEnv.EXPO_PUBLIC_API_BASE_URL);
  const username = mergedEnv.ODDSEYE_MOBILE_SMOKE_USERNAME || "admin";
  const password = mergedEnv.ODDSEYE_MOBILE_SMOKE_PASSWORD || mergedEnv.ODDSEYE_VERIFY_PASSWORD;
  if (!password) {
    throw new Error("set ODDSEYE_MOBILE_SMOKE_PASSWORD or ODDSEYE_VERIFY_PASSWORD");
  }

  const checks = [];
  checks.push({ name: "env", detail: `EXPO_PUBLIC_API_BASE_URL=${baseUrl}` });

  requireExpoConfig(root);
  checks.push({ name: "expo_config", detail: "Expo config is compatible with Expo Go" });

  const health = await requestJson(fetchImpl, "GET", `${baseUrl}/health`);
  if (health.status !== "ok") {
    throw new Error("health check did not return status=ok");
  }
  checks.push({ name: "health", detail: "backend health returned ok" });

  const login = await requestJson(fetchImpl, "POST", `${baseUrl}/auth/login`, {
    body: JSON.stringify({ username, password }),
    headers: { "Content-Type": "application/json" },
  });
  if (typeof login.access_token !== "string" || !login.access_token) {
    throw new Error("login response did not include access_token");
  }
  checks.push({ name: "login", detail: "backend issued bearer token" });

  const currentUser = await requestJson(fetchImpl, "GET", `${baseUrl}/auth/me`, {
    headers: { Authorization: `Bearer ${login.access_token}` },
  });
  if (currentUser.username !== username) {
    throw new Error(`auth/me returned ${currentUser.username}; expected ${username}`);
  }
  if (typeof currentUser.role !== "string" || !currentUser.role) {
    throw new Error("auth/me did not return a role");
  }
  checks.push({ name: "auth_me", detail: `${username} token resolves to configured user` });

  return checks;
}

function normalizeDeployedApiUrl(value) {
  if (!value) {
    throw new Error("EXPO_PUBLIC_API_BASE_URL is required for Expo Go smoke verification");
  }
  const trimmed = String(value).trim().replace(/\/+$/, "");
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error("EXPO_PUBLIC_API_BASE_URL must be a valid URL");
  }
  if (parsed.protocol !== "https:") {
    throw new Error("EXPO_PUBLIC_API_BASE_URL must use https for deployed Expo Go verification");
  }
  return trimmed;
}

function requireExpoConfig(root) {
  const appJsonPath = resolve(root, "app.json");
  if (!existsSync(appJsonPath)) {
    throw new Error("app.json is required");
  }
  const appJson = JSON.parse(readFileSync(appJsonPath, "utf8"));
  const expo = appJson.expo;
  if (!expo || expo.name !== "OddsEye") {
    throw new Error("app.json expo.name must be OddsEye");
  }
  if (expo.scheme !== "oddseye") {
    throw new Error("app.json expo.scheme must be oddseye");
  }
  if (expo.ios?.bundleIdentifier !== "fun.oddseye.app") {
    throw new Error("app.json ios.bundleIdentifier must be fun.oddseye.app");
  }
  if (!existsSync(resolve(root, "app"))) {
    throw new Error("Expo Router app directory is required");
  }
}

async function requestJson(fetchImpl, method, url, options = {}) {
  const response = await fetchImpl(url, { ...options, method });
  if (!response.ok) {
    throw new Error(`${method} ${url} failed with ${response.status} ${response.statusText || ""}`.trim());
  }
  const payload = await response.json();
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error(`${method} ${url} returned unexpected payload`);
  }
  return payload;
}

function unquoteEnvValue(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const checks = await verifyExpoGoSmoke();
    checks.forEach((check) => {
      console.log(`[ok] ${check.name}: ${check.detail}`);
    });
  } catch (error) {
    console.error(`[fail] ${error instanceof Error ? error.message : String(error)}`);
    exit(1);
  }
}
