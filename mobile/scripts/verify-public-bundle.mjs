#!/usr/bin/env node

import { cwd, env, exit } from "node:process";

import {
  buildForbiddenPatterns,
  defaultScanPaths,
  scanSecretFiles,
} from "./secretScan.mjs";

const root = cwd();
const paths = process.argv.slice(2);
const scanPaths = paths.length > 0 ? paths : defaultScanPaths(root);
const patterns = buildForbiddenPatterns(env.ODDSEYE_FORBIDDEN_BUNDLE_STRINGS || "");
const findings = scanSecretFiles(root, scanPaths, patterns);

if (findings.length > 0) {
  console.error("[fail] Mobile public bundle secret scan found forbidden content:");
  findings.forEach((finding) => {
    console.error(`- ${finding.path}: ${finding.label}`);
  });
  exit(1);
}

console.log(`[ok] Mobile public bundle secret scan passed (${scanPaths.join(", ")})`);
