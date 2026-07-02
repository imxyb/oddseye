import * as SecureStore from "expo-secure-store";

const ACCESS_TOKEN_KEY = "access_token";

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getApiBaseUrl(): string {
  const baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;

  if (!baseUrl) {
    throw new Error("EXPO_PUBLIC_API_BASE_URL is not configured");
  }

  return baseUrl.replace(/\/+$/, "");
}

function toApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${normalizedPath}`;
}

function toHeaderRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) {
    return {};
  }

  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }

  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }

  return { ...headers };
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  const headers = toHeaderRecord(options.headers);

  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }

  if (!headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(toApiUrl(path), {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function toApiError(response: Response): Promise<ApiError> {
  const fallback = "Request failed";
  const text = await response.text();
  if (!text) {
    return new ApiError(response.status, fallback);
  }

  try {
    const detail = JSON.parse(text) as unknown;
    return new ApiError(response.status, messageFromDetail(detail) ?? fallback, detail);
  } catch {
    return new ApiError(response.status, fallback);
  }
}

function messageFromDetail(detail: unknown): string | undefined {
  if (!detail || typeof detail !== "object" || !("detail" in detail)) {
    return undefined;
  }

  const value = (detail as { detail: unknown }).detail;
  if (typeof value === "string") {
    return value;
  }

  return undefined;
}

export { ACCESS_TOKEN_KEY };
