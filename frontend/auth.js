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
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!AUTH.getToken();
  },

  /**
   * Logout - clear token and user data
   */
  logout() {
    localStorage.removeItem(AUTH.TOKEN_KEY);
    localStorage.removeItem(AUTH.USER_KEY);
    console.log("✓ Logged out");
    window.location.href = "login.html";
  },

  /**
   * Get authorization header
   */
  getAuthHeader() {
    const token = AUTH.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
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

      // Fetch full profile to get all user data including name
      try {
        const profileResponse = await fetch(`${AUTH.API_BASE}/api/auth/profile`, {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (profileResponse.ok) {
          const profile = await profileResponse.json();
          AUTH.saveToken(data.access_token, {
            user_id: profile._id || data.user_id,
            email: profile.email || data.email,
            name: profile.name || data.name || "User",
          });
        }
      } catch (e) {
        console.warn("Could not fetch full profile:", e);
      }

      return { success: true, data };
    } catch (error) {
      console.error("Login error:", error);
      return { success: false, error: error.message };
    }
  },

  /**
   * Get current user profile
   */
  async getProfile() {
    try {
      const response = await fetch(`${AUTH.API_BASE}/api/auth/profile`, {
        headers: AUTH.getAuthHeader(),
      });

      if (!response.ok) throw new Error("Failed to fetch profile");

      return await response.json();
    } catch (error) {
      console.error("Get profile error:", error);
      return null;
    }
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

    return fetch(`${AUTH.API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
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

      return await response.json();
    } catch (error) {
      console.error("Get history error:", error);
      return { history: [], error: error.message };
    }
  },

  /**
   * Upload image with authentication
   */
  async uploadImage(file, topK = 8) {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = AUTH.getToken();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const response = await fetch(
        `${AUTH.API_BASE}/api/recommend/image?top_k=${topK}`,
        {
          method: "POST",
          headers,
          body: formData,
        }
      );

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
      console.error("Upload image error:", error);
      return { error: error.message };
    }
  },

  /**
   * Chat with AI stylist
   */
  async chat(message) {
    try {
      const response = await AUTH.call(
        `/api/chat?message=${encodeURIComponent(message)}`,
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
