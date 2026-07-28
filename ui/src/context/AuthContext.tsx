import React, { createContext, useContext, useState, useEffect } from 'react';

export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  permitted_matters: string[];
  token: string;
  created_at?: string;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  login: (email: string, password: str) => Promise<boolean>;
  signup: (email: string, full_name: str, password: str, role: str, permitted_matters: str[]) => Promise<boolean>;
  logout: () => void;
  isLoading: boolean;
  error: string | null;
}

type str = string;

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('lexicon_auth_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = async (authToken: string) => {
    try {
      const res = await fetch('/auth/me', {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const profile = await res.json();
        setUser({ ...profile, token: authToken });
      } else {
        logout();
      }
    } catch (e) {
      console.error('Failed to fetch user profile', e);
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchProfile(token);
    } else {
      setIsLoading(false);
    }
  }, [token]);

  const login = async (email: str, password: str): Promise<boolean> => {
    setError(null);
    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (res.ok) {
        const data: UserProfile = await res.json();
        setUser(data);
        setToken(data.token);
        localStorage.setItem('lexicon_auth_token', data.token);
        return true;
      } else {
        const err = await res.json();
        setError(err.detail || 'Login failed');
        return false;
      }
    } catch (e: any) {
      setError(e.message || 'Login error');
      return false;
    }
  };

  const signup = async (
    email: str,
    full_name: str,
    password: str,
    role: str,
    permitted_matters: str[]
  ): Promise<boolean> => {
    setError(null);
    try {
      const res = await fetch('/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          full_name,
          password,
          role,
          permitted_matters,
        }),
      });

      if (res.ok) {
        const data: UserProfile = await res.json();
        setUser(data);
        setToken(data.token);
        localStorage.setItem('lexicon_auth_token', data.token);
        return true;
      } else {
        const err = await res.json();
        setError(err.detail || 'Sign up failed');
        return false;
      }
    } catch (e: any) {
      setError(e.message || 'Sign up error');
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('lexicon_auth_token');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        signup,
        logout,
        isLoading,
        error,
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
