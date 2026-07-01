import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { relative, resolve } from "node:path";

const DEFAULT_SECRET_ENV_NAMES = [
  "CODEX_API_KEY",
  "JWT_SECRET",
  "DATABASE_URL",
  "REDIS_URL",
];

const DEFAULT_TEXT_EXTENSIONS = new Set([
  "",
  ".bundle",
  ".cjs",
  ".html",
  ".js",
  ".json",
  ".map",
  ".mjs",
  ".ts",
  ".tsx",
  ".txt",
]);

const IGNORED_DIRECTORIES = new Set([
  ".expo",
  ".git",
  "android",
  "coverage",
  "ios",
  "node_modules",
]);

export function buildForbiddenPatterns(extraValues = "") {
  const patterns = DEFAULT_SECRET_ENV_NAMES.map((name) => ({
    label: `backend secret env name: ${name}`,
    value: name,
  }));

  splitExtraValues(extraValues).forEach((value, index) => {
    patterns.push({
      label: `forbidden secret value #${index + 1}`,
      value,
    });
  });

  return patterns;
}

export function scanSecretFiles(rootDir, paths, patterns) {
  const root = resolve(rootDir);
  const files = collectFiles(root, paths);
  const findings = [];

  for (const file of files) {
    const content = readFileSync(file, "utf8");
    for (const pattern of patterns) {
      if (content.includes(pattern.value)) {
        findings.push({
          label: pattern.label,
          path: relative(root, file),
        });
      }
    }
  }

  return findings;
}

export function defaultScanPaths(rootDir) {
  return [
    "app",
    "app.json",
    "babel.config.js",
    "src/api",
    "src/components",
    "src/stores",
    "src/theme.ts",
    "src/utils",
    "dist",
  ].filter((path) => existsSync(resolve(rootDir, path)));
}

function collectFiles(root, paths) {
  const files = [];
  for (const path of paths) {
    const resolved = resolve(root, path);
    if (!existsSync(resolved)) {
      continue;
    }
    collectPath(resolved, files);
  }
  return files;
}

function collectPath(path, files) {
  const stats = statSync(path);
  if (stats.isDirectory()) {
    if (IGNORED_DIRECTORIES.has(path.split(/[/\\]/).at(-1))) {
      return;
    }
    for (const entry of readdirSync(path)) {
      collectPath(resolve(path, entry), files);
    }
    return;
  }
  if (stats.isFile() && isTextFile(path)) {
    files.push(path);
  }
}

function isTextFile(path) {
  const match = path.match(/(\.[^.]+)$/);
  const extension = match ? match[1] : "";
  return DEFAULT_TEXT_EXTENSIONS.has(extension);
}

function splitExtraValues(extraValues) {
  return String(extraValues)
    .split(/[\n,]/)
    .map((value) => value.trim())
    .filter((value) => value.length >= 8);
}
