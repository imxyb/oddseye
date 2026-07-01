import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

import { ACCESS_TOKEN_KEY } from "../api/client";
import { getMe, loginRequest } from "../api/auth";
import type { User } from "../api/types";

type AuthStatus = "idle" | "bootstrapping" | "authenticated" | "anonymous";

interface AuthState {
  token: string | null;
  user: User | null;
  status: AuthStatus;
  error: string | null;
  isBootstrapped: boolean;
  isAuthenticated: boolean;
  bootstrap: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  status: "idle",
  error: null,
  isBootstrapped: false,
  isAuthenticated: false,

  bootstrap: async () => {
    set({ status: "bootstrapping", error: null });

    const token = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);

    if (!token) {
      set({
        token: null,
        user: null,
        status: "anonymous",
        isAuthenticated: false,
        isBootstrapped: true,
      });
      return;
    }

    try {
      const user = await getMe();
      set({
        token,
        user,
        status: "authenticated",
        error: null,
        isAuthenticated: true,
        isBootstrapped: true,
      });
    } catch (error) {
      await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
      set({
        token: null,
        user: null,
        status: "anonymous",
        error: error instanceof Error ? error.message : "Session expired",
        isAuthenticated: false,
        isBootstrapped: true,
      });
    }
  },

  login: async (username: string, password: string) => {
    set({ status: "bootstrapping", error: null });

    try {
      const data = await loginRequest(username, password);
      await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, data.access_token);
      set({
        token: data.access_token,
        user: data.user,
        status: "authenticated",
        error: null,
        isAuthenticated: true,
        isBootstrapped: true,
      });
    } catch (error) {
      set({
        token: null,
        user: null,
        status: "anonymous",
        error: error instanceof Error ? error.message : "Login failed",
        isAuthenticated: false,
        isBootstrapped: true,
      });
      throw error;
    }
  },

  logout: async () => {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    set({
      token: null,
      user: null,
      status: "anonymous",
      error: null,
      isAuthenticated: false,
      isBootstrapped: true,
    });
  },
}));
