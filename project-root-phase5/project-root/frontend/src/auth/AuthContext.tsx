import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest, register as registerRequest } from "@/api/authApi";
import { getStoredRefreshToken, onUnauthorized, setAccessToken, setStoredRefreshToken, clearTokens } from "@/api/client";
import type { LoginPayload, RegisterPayload, User } from "@/types/auth";

interface AuthContextValue {
  user: User | null;
  // True only while the app is figuring out, on first load, whether a
  // stored refresh token is still good — not a general "is anything
  // loading" flag. Individual pages handle their own request loading
  // states separately.
  isInitializing: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  // On first load: if a refresh token survived from a previous session,
  // silently exchange it for a fresh access token and load the profile —
  // otherwise the user starts logged out, which is correct.
  useEffect(() => {
    async function bootstrap() {
      const storedRefreshToken = getStoredRefreshToken();
      if (!storedRefreshToken) {
        setIsInitializing(false);
        return;
      }
      try {
        // Reuse the client's own refresh path indirectly: making any
        // authenticated call while accessToken is null will 401 and the
        // client's interceptor will refresh automatically. /auth/me is a
        // convenient cheap call for this.
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
      } catch {
        clearTokens();
        setUser(null);
      } finally {
        setIsInitializing(false);
      }
    }
    bootstrap();
  }, []);

  // If any request anywhere gets a 401 it can't recover from (refresh
  // token itself invalid/expired/revoked), the api client clears tokens
  // and tells us here — so the UI reflects "logged out" immediately
  // rather than only on the next manual action.
  useEffect(() => {
    return onUnauthorized(() => setUser(null));
  }, []);

  async function login(payload: LoginPayload) {
    const tokens = await loginRequest(payload);
    setAccessToken(tokens.access_token);
    setStoredRefreshToken(tokens.refresh_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
  }

  async function register(payload: RegisterPayload): Promise<User> {
    return registerRequest(payload);
  }

  async function logout() {
    const refreshToken = getStoredRefreshToken();
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken);
      } catch {
        // Already invalid/expired — nothing to revoke, fall through and
        // clear local state anyway.
      }
    }
    clearTokens();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isInitializing, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
