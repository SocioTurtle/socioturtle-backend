import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiClient } from "../api/client";
import { authApi } from "../api/endpoints";
import type { LoginPayload, SignupPayload, User } from "../types";

interface AuthContextValue {
  user: User | null;
  initialising: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  /** Re-read the current user after tokens are set outside this hook. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  client,
  children,
}: {
  client: ApiClient;
  children: ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [initialising, setInitialising] = useState(true);
  const api = useMemo(() => authApi(client), [client]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (await client.hasSession()) {
        try {
          const current = await api.me();
          if (!cancelled) setUser(current);
        } catch {
          await client.clearTokens();
        }
      }
      if (!cancelled) setInitialising(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [api, client]);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const tokens = await api.login(payload);
      await client.saveTokens(tokens);
      setUser(tokens.user);
    },
    [api, client],
  );

  const signup = useCallback(
    async (payload: SignupPayload) => {
      const tokens = await api.signup(payload);
      await client.saveTokens(tokens);
      setUser(tokens.user);
    },
    [api, client],
  );

  const logout = useCallback(async () => {
    await client.clearTokens();
    setUser(null);
  }, [client]);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      await client.clearTokens();
      setUser(null);
    }
  }, [api, client]);

  const value = useMemo(
    () => ({ user, initialising, login, signup, logout, refreshUser }),
    [user, initialising, login, signup, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside an AuthProvider");
  return context;
}
