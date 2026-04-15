/**
 * Authentication Module - Frontend
 * ================================
 * Handles login, registration, token management, and protected API calls.
 * Tokens are stored in localStorage and auto-included in requests.
 */

const AUTH = {
  // Configuration
  TOKEN_KEY: "dressmate_token",
  USER_KEY: "dressmate_user",
  API_BASE: "http://localhost:8000",

  // ──────────────────────────────────────────────────────────────────────────
  // Token Management
  // ──────────────────────────────────────────────────────────────────────────

  /**
   * Save token to localStorage
   */
  saveToken(token, userData) {
    localStorage.setItem(AUTH.TOKEN_KEY, token);
    localStorage.setItem(AUTH.USER_KEY, JSON.stringify(userData));
    console.log("✓ Token saved:", userData.email);
  },

  /**
   * Clear auth session without forcing page navigation.
   */
  clearSession() {
    localStorage.removeItem(AUTH.TOKEN_KEY);
    localStorage.removeItem(AUTH.USER_KEY);
  },

  /**
   * Get token from localStorage
   */
  getToken() {
    return localStorage.getItem(AUTH.TOKEN_KEY);
  },

  /**
   * Get stored user data
   */
  getUser() {
    const user = localStorage.getItem(AUTH.USER_KEY);
    return user ? JSON.parse(user) : null;
  },

  /**
   * Decode JWT payload safely.
   */
  decodeToken(token) {
    try {
      const payloadPart = token.split(".")[1];
      if (!payloadPart) return null;
      const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
      const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
      const payloadJson = decodeURIComponent(
        atob(padded)
          .split("")
          .map((c) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`)
          .join("")
      );
      return JSON.parse(payloadJson);
    } catch {
      return null;
    }
  },

  /**
   * Returns true only when token exists and is not expired.
   */
  hasValidToken() {
    const token = AUTH.getToken();
    if (!token) return false;

    const payload = AUTH.decodeToken(token);
    if (!payload || !payload.exp) return false;

    const now = Math.floor(Date.now() / 1000);
    return payload.exp > now;
  },

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    const isValid = AUTH.hasValidToken();
    if (!isValid && AUTH.getToken()) {
      AUTH.clearSession();
    }
    return isValid;
  },

  /**
   * Logout - clear token and user data
   */
  logout() {
    AUTH.clearSession();
    console.log("✓ Logged out");
    window.location.href = "login.html";
  },

  /**
   * Get authorization header
   */
  getAuthHeader() {
    if (!AUTH.isAuthenticated()) return {};
    const token = AUTH.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  },

  /**
   * Fetch profile from backend and refresh local cached user.
   */
  async refreshProfile() {
    if (!AUTH.isAuthenticated()) return null;
    try {
      const response = await fetch(`${AUTH.API_BASE}/api/auth/profile`, {
        headers: AUTH.getAuthHeader(),
      });

      if (response.status === 401) {
        AUTH.clearSession();
        return null;
      }

      if (!response.ok) return AUTH.getUser();

      const profile = await response.json();
      const token = AUTH.getToken();
      if (token) {
        AUTH.saveToken(token, {
          user_id: profile.user_id,
          email: profile.email,
          name: profile.name || "User",
        });
      }
      return profile;
    } catch (error) {
      console.error("Refresh profile error:", error);
      return AUTH.getUser();
    }
  },

  // ──────────────────────────────────────────────────────────────────────────
  // Authentication Endpoints
  // ──────────────────────────────────────────────────────────────────────────

  /**
   * Register new user
   */
  async register(email, password, name = "User") {
    try {
      const response = await fetch(`${AUTH.API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Registration failed");
      }

      const data = await response.json();
      AUTH.saveToken(data.access_token, {
        user_id: data.user_id,
        email: data.email,
        name: name,
      });

      await AUTH.refreshProfile();

      return { success: true, data };
    } catch (error) {
      console.error("Registration error:", error);
      return { success: false, error: error.message };
    }
  },

  /**
   * Login user
   */
  async login(email, password) {
    try {
      const response = await fetch(`${AUTH.API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Login failed");
      }

      const data = await response.json();
      // Save token first
      AUTH.saveToken(data.access_token, {
        user_id: data.user_id,
        email: data.email,
        name: data.name || "User", // Use name from response if available
      });

      await AUTH.refreshProfile();

      return { success: true, data };
    } catch (error) {
      console.error("Login error:", error);
      return { success: false, error: error.message };
    }
  },

  /**
   * Get current user profile
   */
  getProfile() {
    return AUTH.getUser();
  },

  // ──────────────────────────────────────────────────────────────────────────
  // Protected API Calls
  // ──────────────────────────────────────────────────────────────────────────

  /**
   * Make authenticated API call
   */
  async call(endpoint, options = {}) {
    const headers = {
      ...options.headers,
      ...AUTH.getAuthHeader(),
    };

    const response = await fetch(`${AUTH.API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      AUTH.clearSession();
    }

    return response;
  },

  /**
   * Get recommendation history
   */
  async getHistory(limit = 20) {
    try {
      const response = await AUTH.call(
        `/api/history?limit=${limit}`
      );

      if (!response.ok) throw new Error("Failed to fetch history");

      const data = await response.json();
      return data.history || [];
    } catch (error) {
      console.error("Get history error:", error);
      return [];
    }
  },

  /**
   * Upload image with authentication
   */
  async uploadImage(file, topK = 8, timeoutMs = 120000) {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = AUTH.getToken();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      let response;
      try {
        response = await fetch(
          `${AUTH.API_BASE}/api/recommend/image?top_k=${topK}`,
          {
            method: "POST",
            headers,
            body: formData,
            signal: controller.signal,
          }
        );
      } finally {
        clearTimeout(timeoutId);
      }

      if (!response.ok) {
        const errorText = await response.text();
        let errorDetail = "Unknown error";
        try {
          const errorJson = JSON.parse(errorText);
          errorDetail = errorJson.detail || errorJson.error || errorText;
        } catch {
          errorDetail = errorText || `HTTP ${response.status}`;
        }
        throw new Error(`Image upload failed: ${errorDetail}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === "AbortError") {
        return { error: `Image upload timed out after ${Math.round(timeoutMs / 1000)} seconds.` };
      }
      console.error("Upload image error:", error);
      return { error: error.message };
    }
  },

  /**
   * Chat with AI stylist
   */
  async chat(message, history = "") {
    try {
      const params = new URLSearchParams();
      params.append('message', message);
      if (history) {
        params.append('history', history);
      }

      const response = await AUTH.call(
        `/api/chat?${params.toString()}`,
        { method: "POST" }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Chat failed");
      }

      return await response.json();
    } catch (error) {
      console.error("Chat error:", error);
      return { error: error.message };
    }
  },
};

// ──────────────────────────────────────────────────────────────────────────
// Page Protection Middleware
// ──────────────────────────────────────────────────────────────────────────

/**
 * Redirect to login if not authenticated
 */
function requireAuth() {
  if (!AUTH.isAuthenticated()) {
    window.location.href = "login.html";
    return false;
  }
  return true;
}

/**
 * Redirect to home if already authenticated
 */
function redirectIfAuth() {
  if (AUTH.isAuthenticated()) {
    window.location.href = "index.html";
    return false;
  }
  return true;
}

/**
 * Display user info in header/navbar
 */
function displayUserInfo() {
  const user = AUTH.getUser();
  if (!user) return;

  const userNameElement = document.getElementById("user-name");
  const userEmailElement = document.getElementById("user-email");

  if (userNameElement) userNameElement.textContent = user.name || user.email;
  if (userEmailElement) userEmailElement.textContent = user.email;
}

/**
 * Setup logout button
 */
function setupLogoutButton() {
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", (e) => {
      e.preventDefault();
      AUTH.logout();
    });
  }
}
