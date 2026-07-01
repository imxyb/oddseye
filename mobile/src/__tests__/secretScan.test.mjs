import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  buildForbiddenPatterns,
  scanSecretFiles,
} from "../../scripts/secretScan.mjs";

describe("mobile public bundle secret scan", () => {
  it("reports backend secret variable names without exposing the matched value", () => {
    const root = mkdtempSync(join(tmpdir(), "oddseye-secret-scan-"));
    try {
      writeFileSync(
        join(root, "bundle.js"),
        "globalThis.process = { env: { CODEX_API_KEY: 'bad' } };",
      );

      const findings = scanSecretFiles(root, ["bundle.js"], buildForbiddenPatterns());

      expect(findings).toEqual([
        {
          label: "backend secret env name: CODEX_API_KEY",
          path: "bundle.js",
        },
      ]);
    } finally {
      rmSync(root, { force: true, recursive: true });
    }
  });

  it("allows the public Expo API base URL setting", () => {
    const root = mkdtempSync(join(tmpdir(), "oddseye-secret-scan-"));
    try {
      writeFileSync(
        join(root, "bundle.js"),
        "process.env.EXPO_PUBLIC_API_BASE_URL = 'https://oddseye.fun';",
      );

      const findings = scanSecretFiles(root, ["bundle.js"], buildForbiddenPatterns());

      expect(findings).toEqual([]);
    } finally {
      rmSync(root, { force: true, recursive: true });
    }
  });

  it("checks caller-provided secret values from the environment", () => {
    const root = mkdtempSync(join(tmpdir(), "oddseye-secret-scan-"));
    try {
      writeFileSync(join(root, "main.js"), "const leaked = 'super-secret-token';");

      const findings = scanSecretFiles(
        root,
        ["main.js"],
        buildForbiddenPatterns("super-secret-token"),
      );

      expect(findings).toEqual([
        {
          label: "forbidden secret value #1",
          path: "main.js",
        },
      ]);
    } finally {
      rmSync(root, { force: true, recursive: true });
    }
  });
});
