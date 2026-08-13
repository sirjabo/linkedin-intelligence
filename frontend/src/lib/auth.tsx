"use client";
import React, { createContext, useContext, useEffect, useState } from "react";

interface AuthContextValue {
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  token: null,
  login: () => {},
  logout: () => {},
  isLoading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("li_token");
    if (stored) setToken(stored);
    setIsLoading(false);
  }, []);

  function login(t: string) {
    localStorage.setItem("li_token", t);
    setToken(t);
  }

  function logout() {
    localStorage.removeItem("li_token");
    setToken(null);
  }

  return (
    <AuthContext.Provider value={{ token, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
