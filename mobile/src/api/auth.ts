import { apiFetch } from "./client";
import type { LoginResponse, User } from "./types";

export function loginRequest(username: string, password: string) {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getMe() {
  return apiFetch<User>("/auth/me");
}
