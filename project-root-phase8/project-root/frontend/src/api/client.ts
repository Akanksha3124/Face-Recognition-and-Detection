/**
 * Axios instance with JWT handling.
 *
 * Token storage trade-off (worth knowing, not hiding): the refresh token
 * lives in localStorage so a page reload doesn't force a re-login, and
 * the access token lives only in memory (this module's state). Neither
 * is as safe as an httpOnly cookie against XSS — the backend currently
 * returns both tokens in the JSON response body rather than setting a
 * cookie, so this is the best available option without a backend change.
 * Moving refresh-token storage to an httpOnly cookie is a reasonable
 * Phase 19 (security hardening) upgrade, not something to solve here.
 *
 * On 401, this client attempts exactly one silent refresh-and-retry
 * before giving up and treating the session as logged out. Concurrent
 * 401s (e.g. several requests in flight at once) share a single
 * in-flight refresh call rather than each triggering their own.
 */
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { TokenPair } from "@/types/auth";

const REFRESH_TOKEN_STORAGE_KEY = "refresh_token";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
}

export function setStoredRefreshToken(token: string | null): void {
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
  }
}

export function clearTokens(): void {
  setAccessToken(null);
  setStoredRefreshToken(null);
}

// Callbacks AuthContext registers to hear about a forced logout (e.g. the
// refresh token itself expired/was revoked) that didn't originate from
// the user clicking "log out" — so the UI can react (clear user state,
// redirect to /login) no matter which request triggered it.
type UnauthorizedListener = () => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();

export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

function notifyUnauthorized(): void {
  clearTokens();
  unauthorizedListeners.forEach((listener) => listener());
}

export const apiClient = axios.create({ baseURL });

// A plain axios instance (no interceptors) for the refresh call itself —
// using `apiClient` here would recurse through the response interceptor.
const rawClient = axios.create({ baseURL });

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const storedRefreshToken = getStoredRefreshToken();
  if (!storedRefreshToken) return null;

  try {
    const response = await rawClient.post<TokenPair>("/auth/refresh", {
      refresh_token: storedRefreshToken,
    });
    setAccessToken(response.data.access_token);
    setStoredRefreshToken(response.data.refresh_token);
    return response.data.access_token;
  } catch {
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    const isAuthEndpoint = originalRequest?.url?.includes("/auth/login") || originalRequest?.url?.includes("/auth/refresh");

    if (error.response?.status === 401 && originalRequest && !originalRequest._retried && !isAuthEndpoint) {
      originalRequest._retried = true;

      // Share one in-flight refresh across concurrent 401s instead of
      // each request racing to refresh independently.
      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newAccessToken = await refreshPromise;

      if (newAccessToken) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      }
      notifyUnauthorized();
    }

    return Promise.reject(error);
  }
);
