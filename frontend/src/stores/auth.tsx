import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from '../api/client';

interface AuthState {
  token: string | null;
  username: string | null;
  isAdmin: boolean;
  loading: boolean;
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: localStorage.getItem('token'),
    username: localStorage.getItem('username'),
    isAdmin: localStorage.getItem('isAdmin') === 'true',
    loading: true,
  });

  useEffect(() => {
    if (state.token) {
      api.getMe()
        .then((user) => {
          setState((s) => ({ ...s, username: user.username, isAdmin: user.is_admin, loading: false }));
          localStorage.setItem('username', user.username);
          localStorage.setItem('isAdmin', String(user.is_admin));
        })
        .catch(() => {
          localStorage.clear();
          setState({ token: null, username: null, isAdmin: false, loading: false });
        });
    } else {
      setState((s) => ({ ...s, loading: false }));
    }
  }, []);

  const login = async (username: string, password: string) => {
    const resp = await api.login(username, password);
    localStorage.setItem('token', resp.access_token);
    localStorage.setItem('username', resp.username);
    localStorage.setItem('isAdmin', String(resp.is_admin));
    setState({ token: resp.access_token, username: resp.username, isAdmin: resp.is_admin, loading: false });
  };

  const register = async (username: string, password: string) => {
    const resp = await api.register(username, password);
    localStorage.setItem('token', resp.access_token);
    localStorage.setItem('username', resp.username);
    localStorage.setItem('isAdmin', String(resp.is_admin));
    setState({ token: resp.access_token, username: resp.username, isAdmin: resp.is_admin, loading: false });
  };

  const logout = () => {
    localStorage.clear();
    setState({ token: null, username: null, isAdmin: false, loading: false });
  };

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
