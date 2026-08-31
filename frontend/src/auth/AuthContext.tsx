import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { api, type UserProfile } from '../api/client';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  role: 'ADMIN' | 'OPS' | 'VIEWER' | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<UserProfile>;
  logout: () => void;
  hasRole: (roles: ('ADMIN' | 'OPS' | 'VIEWER')[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('recoverai_token'));
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('recoverai_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Validate session on mount if token exists
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('recoverai_token');
      if (storedToken) {
        try {
          const profile = await api.getMe();
          setUser(profile);
          localStorage.setItem('recoverai_user', JSON.stringify(profile));
        } catch {
          // Token invalid or expired
          logout();
        }
      }
      setIsLoading(false);
    };

    initAuth();

    // Listen for 401 unauthorized events dispatched from client.ts
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener('recoverai:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('recoverai:unauthorized', handleUnauthorized);
  }, []);

  const login = async (email: string, password: string): Promise<UserProfile> => {
    const response = await api.login({ email, password });
    setToken(response.access_token);
    setUser(response.user);
    localStorage.setItem('recoverai_token', response.access_token);
    localStorage.setItem('recoverai_user', JSON.stringify(response.user));
    return response.user;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('recoverai_token');
    localStorage.removeItem('recoverai_user');
    api.logout().catch(() => {});
  };

  const hasRole = (roles: ('ADMIN' | 'OPS' | 'VIEWER')[]): boolean => {
    if (!user || !user.role) return false;
    return roles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        role: user?.role || null,
        isLoading,
        login,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
