(function () {
  const NAV_ITEMS = [
    { key: "home", href: "index.html", label: "Home" },
    { key: "upload", href: "image_upload_page.html", label: "Upload" },
    { key: "browse", href: "browse_products.html", label: "Browse" },
    { key: "style", href: "style_match.html", label: "Style Match" },
    { key: "wardrobe", href: "my_wardrobe.html", label: "My Wardrobe" },
    { key: "stylist", href: "gemini_stylist.html", label: "AI Stylist" },
  ];

  function readStoredUser() {
    try {
      const raw = localStorage.getItem("dressmate_user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function readTokenPayload() {
    try {
      const token = localStorage.getItem("dressmate_token");
      if (!token) return null;
      const payloadPart = token.split(".")[1];
      if (!payloadPart) return null;
      const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
      const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
      return JSON.parse(atob(padded));
    } catch {
      return null;
    }
  }

  function getSessionUser() {
    const storedUser = readStoredUser();
    const tokenPayload = readTokenPayload();
    const token = localStorage.getItem("dressmate_token");
    const now = Math.floor(Date.now() / 1000);
    const hasValidToken = !!(token && tokenPayload && tokenPayload.exp && tokenPayload.exp > now);

    if (!hasValidToken) {
      return null;
    }

    return storedUser || {
      user_id: tokenPayload.user_id,
      email: tokenPayload.email || "",
      name: tokenPayload.email ? tokenPayload.email.split("@")[0] : "User",
    };
  }

  function navLink(item, activeKey, mobile) {
    const active = item.key === activeKey;
    const activeClass = mobile ? "text-primary font-bold" : "text-primary border-b-2 border-primary";
    const idleClass = "text-slate-600 hover:text-primary";
    return `<a class="text-sm font-medium transition-colors ${active ? activeClass : idleClass}" href="${item.href}">${item.label}</a>`;
  }

  function userMarkup() {
    const user = getSessionUser();
    const name = user?.name || "Guest";
    const email = user?.email || "Sign in to save your style";
    const actionMarkup = user
      ? `
          <a href="dashboard.html" class="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Dashboard</a>
          <a href="my_wardrobe.html" class="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">My Wardrobe</a>
          <button id="sharedLogoutBtn" class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50">Logout</button>
        `
      : `
          <button id="sharedLoginBtn" class="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Login</button>
        `;

    return `
      <div class="relative">
        <button id="sharedUserButton" class="h-10 w-10 rounded-full bg-primary/15 border-2 border-primary/25 flex items-center justify-center text-primary font-bold hover:border-primary/50 transition-all">
          ${(name || "U").charAt(0).toUpperCase()}
        </button>
        <div id="sharedUserDropdown" class="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-lg py-2 z-40 hidden border border-slate-100">
          <div class="px-4 py-2 border-b border-slate-100">
            <p class="text-sm font-semibold text-slate-900">${name}</p>
            <p class="text-xs text-slate-500">${email}</p>
          </div>
          ${actionMarkup}
        </div>
      </div>
    `;
  }

  function navbarHtml(activeKey) {
    return `
      <header class="flex items-center justify-between border-b border-primary/10 bg-white/80 backdrop-blur-md px-6 py-4 lg:px-20 sticky top-0 z-50">
        <div class="flex items-center gap-3">
          <a href="index.html" class="flex items-center gap-3">
            <div class="bg-primary p-2 rounded-lg text-white"><span class="material-symbols-outlined">apparel</span></div>
            <h2 class="text-slate-900 text-xl font-bold tracking-tight">DressMate</h2>
          </a>
        </div>
        <nav class="hidden md:flex items-center gap-10">
          ${NAV_ITEMS.map((item) => navLink(item, activeKey, false)).join("")}
        </nav>
        <div class="flex items-center gap-4">
          <button id="sharedMenuButton" class="md:hidden flex items-center justify-center rounded-full size-10 text-slate-500 hover:bg-slate-100 transition-colors">
            <span class="material-symbols-outlined">menu</span>
          </button>
          ${userMarkup()}
        </div>
      </header>
      <div id="sharedMobileMenu" class="hidden md:hidden bg-white border-b border-primary/10 px-6 py-4 flex flex-col gap-3">
        ${NAV_ITEMS.map((item) => navLink(item, activeKey, true)).join("")}
      </div>
    `;
  }

  function attachNavbarEvents() {
    const menuButton = document.getElementById("sharedMenuButton");
    const mobileMenu = document.getElementById("sharedMobileMenu");
    const userButton = document.getElementById("sharedUserButton");
    const userDropdown = document.getElementById("sharedUserDropdown");
    const logoutButton = document.getElementById("sharedLogoutBtn");
    const loginButton = document.getElementById("sharedLoginBtn");

    if (menuButton && mobileMenu) {
      menuButton.addEventListener("click", () => mobileMenu.classList.toggle("hidden"));
    }

    if (userButton && userDropdown) {
      userButton.addEventListener("click", (event) => {
        event.stopPropagation();
        userDropdown.classList.toggle("hidden");
      });
      document.addEventListener("click", (event) => {
        if (!event.target.closest("#sharedUserButton") && !event.target.closest("#sharedUserDropdown")) {
          userDropdown.classList.add("hidden");
        }
      });
    }

    if (logoutButton) {
      logoutButton.addEventListener("click", () => {
        if (window.AUTH && AUTH.logout) {
          AUTH.logout();
        } else {
          localStorage.removeItem("dressmate_token");
          localStorage.removeItem("dressmate_user");
          window.location.href = "login.html";
        }
      });
    }

    if (loginButton) {
      loginButton.addEventListener("click", () => {
        window.location.href = "login.html";
      });
    }
  }

  window.initSharedPage = function initSharedPage(options = {}) {
    const { activeNav = "", requireAuth = false } = options;
    const user = getSessionUser();
    if (requireAuth && !user) {
      window.location.href = "login.html";
      return;
    }

    const header = document.querySelector("header");
    const mobileMenu = document.getElementById("mobile-menu");
    if (header) {
      header.insertAdjacentHTML("beforebegin", navbarHtml(activeNav));
      header.remove();
      if (mobileMenu) mobileMenu.remove();
    } else {
      const mount = document.getElementById("appNavbar");
      if (mount) {
        mount.innerHTML = navbarHtml(activeNav);
      } else {
        // If no mount point exists, insert after body opens
        document.body.insertAdjacentHTML("afterbegin", navbarHtml(activeNav));
      }
    }

    attachNavbarEvents();
  };
})();
