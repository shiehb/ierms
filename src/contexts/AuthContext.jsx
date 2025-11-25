import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { loginUser, getProfile } from "../services/api";
import { useNotifications } from "../hooks/useNotifications";
import { API_BASE_URL } from "../config/api";
import { CACHE_CONFIG, CACHE_KEYS, AuthCache, TokenManager } from "./authUtils";
import AuthContext from "./AuthContextObject";

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const notifications = useNotifications();

  const refreshAccessToken = useCallback(async () => {
    const { refresh } = TokenManager.getTokens();
    if (!refresh) {
      throw new Error("No refresh token available");
    }

    const response = await axios.post(`${API_BASE_URL}auth/token/refresh/`, {
      refresh,
    });

    const newAccess = response.data?.access;
    const newRefresh = response.data?.refresh;

    if (!newAccess) {
      throw new Error("Failed to refresh access token");
    }

    TokenManager.setTokens(newAccess, newRefresh || refresh);
    return { access: newAccess, refresh: newRefresh || refresh };
  }, []);

  // Initialize auth state from cache
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const { access, refresh } = TokenManager.getTokens();

        if (!access || !refresh) {
          setLoading(false);
          return;
        }

        // Check if token needs refresh
        if (TokenManager.needsRefresh()) {
          try {
            await refreshAccessToken();
          } catch (refreshError) {
            console.error(
              "Failed to refresh token during initialization:",
              refreshError
            );
            AuthCache.clear();
            TokenManager.clearTokens();
            setLoading(false);
            return;
          }
        }

        // Try to get cached profile first
        const cachedProfile = AuthCache.get(CACHE_KEYS.PROFILE);
        if (cachedProfile) {
          setUser(cachedProfile);
          setAuthenticated(true);
          setLoading(false);
          return;
        }

        // Fetch fresh profile
        const profile = await getProfile();
        setUser(profile);
        setAuthenticated(true);

        // Cache the profile
        AuthCache.set(CACHE_KEYS.PROFILE, profile);
      } catch (error) {
        console.error("Auth initialization failed:", error);
        AuthCache.clear();
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, [refreshAccessToken]);

  const login = useCallback(
    async (email, password) => {
      try {
        setLoading(true);

        const response = await loginUser(email, password);

        // Store tokens
        TokenManager.setTokens(response.access, response.refresh);

        // Fetch and cache user profile
        const profile = await getProfile();
        setUser(profile);
        setAuthenticated(true);

        // Cache profile and login info
        AuthCache.set(CACHE_KEYS.PROFILE, profile);
        AuthCache.set(CACHE_KEYS.LAST_LOGIN, {
          email,
          timestamp: Date.now(),
        });

        notifications.success("Login successful! Welcome back.", {
          title: "Login Successful",
          duration: 3000,
        });

        return {
          user: profile,
          mustChangePassword: response.must_change_password,
        };
      } catch (error) {
        console.error("Login failed:", error);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [notifications]
  );

  const logout = useCallback(async () => {
    try {
      setLoading(true);

      // Call logout API if tokens exist
      const { access, refresh } = TokenManager.getTokens();
      if (refresh) {
        try {
          const headers = {
            "Content-Type": "application/json",
          };
          if (access) {
            headers.Authorization = `Bearer ${access}`;
          }

          await fetch(`${API_BASE_URL}auth/logout/`, {
            method: "POST",
            headers,
            body: JSON.stringify({ refresh }),
          });
        } catch (error) {
          console.warn("Logout API call failed:", error);
        }
      }

      // Clear all auth data
      AuthCache.clear();
      TokenManager.clearTokens();

      // Reset state
      setUser(null);
      setAuthenticated(false);

      notifications.success("Logged out successfully!", {
        title: "Logout Successful",
        duration: 3000,
      });

      // Dispatch logout event for other components
      window.dispatchEvent(new CustomEvent("authLogout"));
    } catch (error) {
      console.error("Logout failed:", error);
      notifications.error("Logout failed!", {
        title: "Logout Error",
        duration: 6000,
      });
    } finally {
      setLoading(false);
    }
  }, [notifications]);

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await getProfile();
      setUser(profile);
      AuthCache.set(CACHE_KEYS.PROFILE, profile);
      return profile;
    } catch (error) {
      console.error("Failed to refresh profile:", error);
      // If profile refresh fails, user might be logged out
      if (error.response?.status === 401) {
        await logout();
      }
      throw error;
    }
  }, [logout]);

  const updateUserPreferences = useCallback(
    (preferences) => {
      if (user) {
        const updatedUser = { ...user, preferences };
        setUser(updatedUser);
        AuthCache.set(CACHE_KEYS.PROFILE, updatedUser);
        AuthCache.set(CACHE_KEYS.USER_PREFERENCES, preferences);
      }
    },
    [user]
  );

  // Auto-refresh profile periodically
  useEffect(() => {
    if (!authenticated) return;

    const interval = setInterval(async () => {
      try {
        // Only refresh if cache is getting old
        const cachedProfile = AuthCache.get(CACHE_KEYS.PROFILE);
        if (!cachedProfile) {
          await refreshProfile();
        }
      } catch (error) {
        console.warn("Auto profile refresh failed:", error);
      }
    }, CACHE_CONFIG.PROFILE_TTL);

    return () => clearInterval(interval);
  }, [authenticated, refreshProfile]);

  const value = {
    user,
    loading,
    authenticated,
    login,
    logout,
    refreshProfile,
    updateUserPreferences,
    // Cache utilities
    cache: AuthCache,
    tokenManager: TokenManager,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
