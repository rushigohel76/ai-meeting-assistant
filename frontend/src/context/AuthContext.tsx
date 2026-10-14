import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRef } from "react";

import {
  ApiError,
  configureApiAuth,
  loginRequest,
  refreshSession,
  setApiAccessToken,
  signupRequest,
} from "../lib/api";

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  accessToken: string | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("unauthenticated");
  // Track an in-flight refresh promise to deduplicate parallel refresh attempts
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);
  // If a refresh has definitively failed (no session), avoid retrying until user logs in
  const refreshFailedRef = useRef<boolean>(false);

  const logout = useCallback(() => {
    setApiAccessToken(null);
    setAccessToken(null);
    // allow future refresh attempts after an explicit logout/login cycle
    refreshFailedRef.current = false;
    setStatus("unauthenticated");
  }, []);

  const refreshAccessToken = useCallback(async () => {
    // If we've already determined there's no valid session, short-circuit
    if (refreshFailedRef.current) return null;

    // If there's already a refresh in progress, return that promise
    if (refreshPromiseRef.current) return refreshPromiseRef.current;

    const p = (async () => {
      try {
        const tokenResponse = await refreshSession();
        // success - clear any failure marker
        refreshFailedRef.current = false;
        setApiAccessToken(tokenResponse.access_token);
        setAccessToken(tokenResponse.access_token);
        setStatus("authenticated");
        return tokenResponse.access_token;
      } catch (err) {
        // treat any error as "no existing session"; avoid retry storms
        refreshFailedRef.current = true;
        setAccessToken(null);
        setApiAccessToken(null);
        setStatus("unauthenticated");
        return null;
      } finally {
        // clear in-flight promise when done
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = p;
    return p;
  }, []);

  useEffect(() => {
    configureApiAuth({
      getAccessToken: () => accessToken,
      setAccessToken: (token) => {
        setAccessToken(token);
        setStatus(token ? "authenticated" : "unauthenticated");
      },
      refreshAccessToken,
      logout,
    });
  }, [accessToken, logout, refreshAccessToken]);

  const login = useCallback(async (email: string, password: string) => {
    const tokenResponse = await loginRequest(email, password);
    setApiAccessToken(tokenResponse.access_token);
    setAccessToken(tokenResponse.access_token);
    // successful login - clear any refresh-failed marker
    refreshFailedRef.current = false;
    setStatus("authenticated");
  }, []);

  const signup = useCallback(
    async (email: string, password: string, fullName: string) => {
      const tokenResponse = await signupRequest(email, password, fullName);
      setApiAccessToken(tokenResponse.access_token);
      setAccessToken(tokenResponse.access_token);
      // successful signup - clear any refresh-failed marker
      refreshFailedRef.current = false;
      setStatus("authenticated");
    },
    [],
  );

  const value = useMemo(
    () => ({
      accessToken,
      status,
      login,
      signup,
      logout,
    }),
    [accessToken, login, logout, signup, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

export function getFriendlyAuthError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) {
    return error.detail;
  }
  return fallback;
}
