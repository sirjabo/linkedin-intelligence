"use client";
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { refreshTokens } from "./api-v2";

interface AuthContextValue {
  token: string | null;
  login: (accessToken: string) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  token: null,
  login: () => {},
  setTokens: () => {},
  logout: () => {},
  isLoading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshingRef = useRef(false);

  useEffect(() => {
    const stored = localStorage.getItem("li_token");
    if (stored) setToken(stored);
    setIsLoading(false);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("li_token");
    localStorage.removeItem("li_refresh_token");
    setToken(null);
  }, []);

  const setTokens = useCallback((accessToken: string, refreshToken: string) => {
    localStorage.setItem("li_token", accessToken);
    localStorage.setItem("li_refresh_token", refreshToken);
    setToken(accessToken);
  }, []);

  const login = useCallback((accessToken: string) => {
    localStorage.setItem("li_token", accessToken);
    setToken(accessToken);
  }, []);

  useEffect(() => {
    async function handleTokenExpired() {
      if (refreshingRef.current) return;
      const storedRefresh = localStorage.getItem("li_refresh_token");
      if (!storedRefresh) { logout(); return; }
      refreshingRef.current = true;
      try {
        const data = await refreshTokens(storedRefresh);
        setTokens(data.access_token, data.refresh_token);
      } catch {
        logout();
      } finally {
        refreshingRef.current = false;
      }
    }

    window.addEventListener("auth:token-expired", handleTokenExpired);
    return () => window.removeEventListener("auth:token-expired", handleTokenExpired);
  }, [logout, setTokens]);

  return (
    <AuthContext.Provider value={{ token, login, setTokens, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
