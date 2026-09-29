import { apiClient } from "@/api/client";
import type { LoginPayload, RegisterPayload, TokenPair, User } from "@/types/auth";

export async function login(payload: LoginPayload): Promise<TokenPair> {
  const response = await apiClient.post<TokenPair>("/auth/login", payload);
  return response.data;
}

export async function register(payload: RegisterPayload): Promise<User> {
  const response = await apiClient.post<User>("/auth/register", payload);
  return response.data;
}

export async function logout(refreshToken: string): Promise<void> {
  // Best-effort: if this fails (e.g. token already expired), the caller
  // still clears local state — there's nothing more to revoke.
  await apiClient.post("/auth/logout", { refresh_token: refreshToken });
}

export async function fetchCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
}
